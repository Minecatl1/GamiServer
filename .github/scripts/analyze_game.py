#!/usr/bin/env python3
"""
Game Analyzer Script for Game Packaging System
Automatically detects executable types, parses launch scripts, and generates metadata.json
"""

import os
import sys
import json
import re
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import shutil


class GameAnalyzer:
    """Analyzes game files and generates metadata for packaging."""
    
    # File types to scan for
    EXECUTABLE_EXTENSIONS = {
        '.appimage': 'appimage',
        '.x86_64': 'x86_64',
        '.exe': 'wine_exe',
        '.jar': 'jar',
        '.love': 'love',
        '.sh': 'shell',
        '.desktop': 'desktop',
        '.cmd': 'batch',
        '.bat': 'batch',
    }
    
    # Launch detection priority (higher = more confident)
    LAUNCH_PRIORITY = {
        'appimage': 100,
        'x86_64': 100,
        'jar': 100,
        'love': 100,
        'desktop_exec': 95,
        'shell': 85,
        'batch_parsed': 95,
        'wine_exe': 80,
        'ambiguous': 50,
    }
    
    # Updater/installer patterns to ignore
    IGNORE_PATTERNS = [
        r'(?i)(updater|update)',
        r'(?i)(uninstall)',
        r'(?i)(crashreport)',
        r'(?i)(vcredist)',
        r'(?i)(runtime)',
    ]
    
    def __init__(self, build_dir: str, repo_name: str):
        """Initialize the analyzer.
        
        Args:
            build_dir: Path to build/game directory
            repo_name: Repository name for metadata
        """
        self.build_dir = Path(build_dir).resolve()
        self.repo_name = repo_name
        self.metadata = {
            'name': repo_name,
            'launch_type': None,
            'launch_target': None,
            'launch_args': '',
            'dependencies': [],
            'confidence': 0,
            'detected_files': [],
        }
        self.found_executables = []
        
    def should_ignore_file(self, filename: str) -> bool:
        """Check if file matches ignore patterns."""
        for pattern in self.IGNORE_PATTERNS:
            if re.search(pattern, filename):
                return True
        return False
    
    def scan_directory(self) -> List[Dict]:
        """Recursively scan directory for executable files.
        
        Returns:
            List of found executable files with metadata
        """
        found = []
        
        if not self.build_dir.exists():
            print(f"Error: Build directory does not exist: {self.build_dir}")
            return found
        
        for root, dirs, files in os.walk(self.build_dir):
            # Skip hidden directories and common non-game paths
            dirs[:] = [d for d in dirs if not d.startswith('.') 
                      and d not in ['node_modules', '__pycache__', '.git']]
            
            for file in files:
                if self.should_ignore_file(file):
                    continue
                
                file_path = Path(root) / file
                ext = file_path.suffix.lower()
                
                if ext in self.EXECUTABLE_EXTENSIONS:
                    file_type = self.EXECUTABLE_EXTENSIONS[ext]
                    rel_path = file_path.relative_to(self.build_dir)
                    
                    found.append({
                        'path': str(rel_path),
                        'filename': file,
                        'type': file_type,
                        'absolute_path': str(file_path),
                    })
                    self.metadata['detected_files'].append(str(rel_path))
        
        self.found_executables = found
        return found
    
    def parse_batch_file(self, file_path: str) -> Tuple[Optional[str], str, int]:
        """Parse Windows .bat/.cmd file to extract launch command.
        
        Args:
            file_path: Path to batch file
            
        Returns:
            Tuple of (launch_target, launch_args, confidence)
        """
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        except Exception as e:
            print(f"Error reading batch file {file_path}: {e}")
            return None, '', 0
        
        # Remove comments and normalize whitespace
        lines = []
        for line in content.split('\n'):
            # Remove batch comments
            line = re.sub(r'::.*$', '', line, flags=re.MULTILINE)
            # Remove REM comments
            line = re.sub(r'(?i)^\s*rem\s+.*$', '', line, flags=re.MULTILINE)
            line = line.strip()
            if line:
                lines.append(line)
        
        content = '\n'.join(lines)
        
        # Pattern matching for various batch launch formats
        patterns = [
            # "%~dp0Game.exe" args
            r'"%~dp0([^"]+\.exe)"\s*(.*?)(?:\s*$|\s*pause|\s*exit)',
            # Game.exe args (with or without start)
            r'(?:start\s*)?(?:""?\s*)?([^"\s]+\.exe)\s+(.*?)(?:\s*$|\s*pause|\s*exit)',
            # call Game.exe
            r'call\s+([^"\s]+\.exe)\s+(.*?)(?:\s*$|\s*pause|\s*exit)',
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                exe_name = match.group(1)
                args = match.group(2) if match.lastindex >= 2 else ''
                
                if not self.should_ignore_file(exe_name):
                    args = args.strip()
                    return exe_name, args, self.LAUNCH_PRIORITY['batch_parsed']
        
        return None, '', 0
    
    def parse_desktop_file(self, file_path: str) -> Tuple[Optional[str], str, int]:
        """Parse .desktop file to extract Exec command.
        
        Args:
            file_path: Path to .desktop file
            
        Returns:
            Tuple of (launch_target, launch_args, confidence)
        """
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        except Exception as e:
            print(f"Error reading desktop file {file_path}: {e}")
            return None, '', 0
        
        # Look for Exec= line
        exec_match = re.search(r'^\s*Exec\s*=\s*(.+?)$', content, re.MULTILINE | re.IGNORECASE)
        
        if exec_match:
            exec_line = exec_match.group(1).strip()
            # Remove field codes like %f, %F, %u, %U, %d, %D, %n, %N, %i, %c, %k, %v
            exec_line = re.sub(r'\s*%[fFuUdDnNickv]\s*', '', exec_line)
            exec_line = exec_line.strip()
            
            # Split command and args
            parts = exec_line.split(None, 1)
            if parts:
                return parts[0], parts[1] if len(parts) > 1 else '', self.LAUNCH_PRIORITY['desktop_exec']
        
        return None, '', 0
    
    def analyze_executables(self) -> None:
        """Analyze found executables and determine best launch method."""
        if not self.found_executables:
            print("No executables found")
            return
        
        # Sort by priority
        priority_order = ['appimage', 'x86_64', 'jar', 'love', 'desktop', 'shell', 'batch', 'wine_exe']
        sorted_exes = sorted(
            self.found_executables,
            key=lambda x: priority_order.index(x['type']) if x['type'] in priority_order else 999
        )
        
        best_choice = None
        best_confidence = 0
        
        for exe in sorted_exes:
            exe_path = exe['absolute_path']
            exe_type = exe['type']
            
            if exe_type == 'appimage':
                best_choice = exe
                best_confidence = 100
                break
            
            elif exe_type == 'x86_64':
                best_choice = exe
                best_confidence = 100
                break
            
            elif exe_type == 'jar':
                best_choice = exe
                best_confidence = 100
                break
            
            elif exe_type == 'love':
                best_choice = exe
                best_confidence = 100
                break
            
            elif exe_type == 'desktop':
                launch_target, launch_args, conf = self.parse_desktop_file(exe_path)
                if launch_target and conf > best_confidence:
                    best_choice = exe
                    best_confidence = conf
                    self.metadata['launch_target'] = launch_target
                    self.metadata['launch_args'] = launch_args
            
            elif exe_type == 'shell':
                if best_confidence < self.LAUNCH_PRIORITY['shell']:
                    best_choice = exe
                    best_confidence = self.LAUNCH_PRIORITY['shell']
            
            elif exe_type == 'batch':
                launch_target, launch_args, conf = self.parse_batch_file(exe_path)
                if launch_target and conf > best_confidence:
                    best_choice = exe
                    best_confidence = conf
                    self.metadata['launch_target'] = launch_target
                    self.metadata['launch_args'] = launch_args
            
            elif exe_type == 'wine_exe':
                if best_confidence < self.LAUNCH_PRIORITY['wine_exe']:
                    best_choice = exe
                    best_confidence = self.LAUNCH_PRIORITY['wine_exe']
        
        if best_choice:
            self._set_metadata_from_choice(best_choice, best_confidence)
    
    def _set_metadata_from_choice(self, choice: Dict, confidence: int) -> None:
        """Set metadata based on selected executable."""
        exe_type = choice['type']
        
        if exe_type == 'appimage':
            self.metadata['launch_type'] = 'appimage'
            self.metadata['launch_target'] = choice['path']
            self.metadata['confidence'] = 100
        
        elif exe_type == 'x86_64':
            self.metadata['launch_type'] = 'x86_64'
            self.metadata['launch_target'] = choice['path']
            self.metadata['confidence'] = 100
        
        elif exe_type == 'jar':
            self.metadata['launch_type'] = 'jar'
            self.metadata['launch_target'] = choice['path']
            self.metadata['confidence'] = 100
            self.metadata['dependencies'].append('java')
        
        elif exe_type == 'love':
            self.metadata['launch_type'] = 'love'
            self.metadata['launch_target'] = choice['path']
            self.metadata['confidence'] = 100
            self.metadata['dependencies'].append('love')
        
        elif exe_type == 'desktop':
            # Already set by parse_desktop_file
            self.metadata['launch_type'] = 'shell'
            self.metadata['confidence'] = confidence
        
        elif exe_type == 'shell':
            self.metadata['launch_type'] = 'shell'
            self.metadata['launch_target'] = choice['path']
            self.metadata['confidence'] = confidence
        
        elif exe_type == 'wine_exe':
            self.metadata['launch_type'] = 'wine'
            self.metadata['launch_target'] = choice['path']
            self.metadata['confidence'] = confidence
            self.metadata['dependencies'].extend(['wine', 'wine32', 'wine64'])
    
    def detect_dependencies(self) -> None:
        """Detect additional dependencies based on launch type."""
        launch_type = self.metadata['launch_type']
        
        # Check for common dependency patterns in detected files
        file_content = '\n'.join(self.metadata['detected_files']).lower()
        
        if 'java' in file_content or launch_type == 'jar':
            if 'java' not in self.metadata['dependencies']:
                self.metadata['dependencies'].append('java')
        
        if launch_type == 'wine':
            if 'wine' not in self.metadata['dependencies']:
                self.metadata['dependencies'].extend(['wine', 'wine32', 'wine64'])
        
        if launch_type == 'love':
            if 'love' not in self.metadata['dependencies']:
                self.metadata['dependencies'].append('love')
        
        # Remove duplicates
        self.metadata['dependencies'] = list(set(self.metadata['dependencies']))
    
    def analyze(self) -> Dict:
        """Run full analysis and return metadata.
        
        Returns:
            Metadata dictionary
        """
        print(f"Scanning directory: {self.build_dir}")
        self.scan_directory()
        
        print(f"Found {len(self.found_executables)} executable(s)")
        for exe in self.found_executables:
            print(f"  - {exe['path']} ({exe['type']})")
        
        self.analyze_executables()
        self.detect_dependencies()
        
        print(f"\nDetected launch type: {self.metadata['launch_type']}")
        print(f"Confidence: {self.metadata['confidence']}%")
        print(f"Dependencies: {self.metadata['dependencies']}")
        
        return self.metadata
    
    def save_metadata(self, output_path: str) -> None:
        """Save metadata to JSON file."""
        try:
            with open(output_path, 'w') as f:
                json.dump(self.metadata, f, indent=2)
            print(f"Metadata saved to {output_path}")
        except Exception as e:
            print(f"Error saving metadata: {e}")
            sys.exit(1)


def main():
    """Main entry point."""
    if len(sys.argv) < 3:
        print("Usage: analyze_game.py <build_dir> <repo_name> [output_file]")
        print("Example: analyze_game.py ./build/game MyGame ./metadata.json")
        sys.exit(1)
    
    build_dir = sys.argv[1]
    repo_name = sys.argv[2]
    output_file = sys.argv[3] if len(sys.argv) > 3 else 'metadata.json'
    
    analyzer = GameAnalyzer(build_dir, repo_name)
    metadata = analyzer.analyze()
    analyzer.save_metadata(output_file)
    
    # Exit with success code
    sys.exit(0)


if __name__ == '__main__':
    main()
