#!/bin/bash
#
# Universal Game Launcher Script Generator
# Generates run_<game>.sh from metadata.json
# This script handles dependency detection, installation prompts, and game execution
#

set -euo pipefail

if [[ $# -lt 2 ]]; then
    echo "Usage: generate_launcher.sh <metadata_json> <output_script> [game_dir]"
    echo "Example: generate_launcher.sh metadata.json run_mygame.sh ."
    exit 1
fi

METADATA_FILE="$1"
OUTPUT_SCRIPT="$2"
GAME_DIR="${3:-.}"

if [[ ! -f "$METADATA_FILE" ]]; then
    echo "Error: metadata file not found: $METADATA_FILE"
    exit 1
fi

# Extract metadata using jq or python json
if command -v jq &> /dev/null; then
    LAUNCH_TYPE=$(jq -r '.launch_type // empty' "$METADATA_FILE")
    LAUNCH_TARGET=$(jq -r '.launch_target // empty' "$METADATA_FILE")
    LAUNCH_ARGS=$(jq -r '.launch_args // ""' "$METADATA_FILE")
    GAME_NAME=$(jq -r '.name // "Game"' "$METADATA_FILE")
    DEPENDENCIES=$(jq -r '.dependencies[]? // empty' "$METADATA_FILE" | tr '\n' ' ')
else
    echo "Error: jq is required but not installed"
    exit 1
fi

if [[ -z "$LAUNCH_TYPE" || -z "$LAUNCH_TARGET" ]]; then
    echo "Error: Could not extract launch configuration from metadata"
    exit 1
fi

cat > "$OUTPUT_SCRIPT" << 'LAUNCHER_EOF'
#!/bin/bash
#
# Auto-generated Game Launcher
# DO NOT EDIT MANUALLY - regenerate using generate_launcher.sh
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
METADATA_FILE="$SCRIPT_DIR/metadata.json"
GAME_DIR="$SCRIPT_DIR"

if [[ ! -f "$METADATA_FILE" ]]; then
    echo "Error: metadata.json not found at $METADATA_FILE"
    exit 1
fi

# Function to detect OS/distro
detect_distro() {
    if [[ -f /etc/os-release ]]; then
        . /etc/os-release
        echo "$ID"
    elif uname -s | grep -qi "FreeBSD"; then
        echo "freebsd"
    else
        echo "unknown"
    fi
}

# Function to install packages
install_package() {
    local distro="$1"
    local package="$2"
    
    echo "Installing $package for $distro..."
    
    case "$distro" in
        ubuntu|debian)
            sudo apt update
            sudo apt install -y "$package"
            ;;
        arch|manjaro)
            sudo pacman -S --noconfirm "$package"
            ;;
        fedora)
            sudo dnf install -y "$package"
            ;;
        opensuse*)
            sudo zypper install -y "$package"
            ;;
        freebsd)
            sudo pkg install -y "$package"
            ;;
        *)
            echo "Unknown distro: $distro"
            return 1
            ;;
    esac
}

# Function to check if command exists
command_exists() {
    command -v "$1" &> /dev/null
}

# Function to prompt for dependency installation
prompt_install_dependency() {
    local dep="$1"
    local distro="$2"
    
    echo "Missing required dependency: $dep"
    read -p "Install it now? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        install_package "$distro" "$dep"
    else
        echo "Warning: $dep is required to run this game"
    fi
}

# Function to check and install dependencies
check_dependencies() {
    local distro="$1"
    local deps_string="$2"
    
    # Parse dependencies
    local deps=($deps_string)
    
    for dep in "${deps[@]}"; do
        case "$dep" in
            wine)
                if ! command_exists wine; then
                    prompt_install_dependency "wine" "$distro"
                fi
                ;;
            wine32)
                if ! command_exists wine; then
                    prompt_install_dependency "wine32" "$distro"
                fi
                ;;
            wine64)
                if ! command_exists wine64; then
                    prompt_install_dependency "wine64" "$distro"
                fi
                ;;
            java)
                if ! command_exists java; then
                    prompt_install_dependency "default-jre" "$distro"
                fi
                ;;
            love)
                if ! command_exists love; then
                    prompt_install_dependency "love" "$distro"
                fi
                ;;
            mono)
                if ! command_exists mono; then
                    prompt_install_dependency "mono" "$distro"
                fi
                ;;
            *)
                echo "Unknown dependency: $dep"
                ;;
        esac
    done
}

# Main execution
main() {
    echo "Starting game launcher..."
    
    DISTRO=$(detect_distro)
    echo "Detected distro: $DISTRO"
    
    # Extract metadata values (these are substituted during generation)
    LAUNCH_TYPE="__LAUNCH_TYPE__"
    LAUNCH_TARGET="__LAUNCH_TARGET__"
    LAUNCH_ARGS="__LAUNCH_ARGS__"
    DEPENDENCIES="__DEPENDENCIES__"
    
    # Check dependencies
    if [[ -n "$DEPENDENCIES" ]]; then
        check_dependencies "$DISTRO" "$DEPENDENCIES"
    fi
    
    # Change to game directory
    cd "$GAME_DIR"
    
    # Prepare launch command
    LAUNCH_CMD=""
    
    case "$LAUNCH_TYPE" in
        wine)
            LAUNCH_CMD="wine \"$LAUNCH_TARGET\" $LAUNCH_ARGS"
            ;;
        jar)
            LAUNCH_CMD="java -jar \"$LAUNCH_TARGET\" $LAUNCH_ARGS"
            ;;
        love)
            LAUNCH_CMD="love \"$LAUNCH_TARGET\" $LAUNCH_ARGS"
            ;;
        appimage)
            LAUNCH_CMD="\"$LAUNCH_TARGET\" $LAUNCH_ARGS"
            chmod +x "$LAUNCH_TARGET" 2>/dev/null || true
            ;;
        x86_64)
            LAUNCH_CMD="\"$LAUNCH_TARGET\" $LAUNCH_ARGS"
            chmod +x "$LAUNCH_TARGET" 2>/dev/null || true
            ;;
        shell)
            LAUNCH_CMD="bash \"$LAUNCH_TARGET\" $LAUNCH_ARGS"
            chmod +x "$LAUNCH_TARGET" 2>/dev/null || true
            ;;
        *)
            echo "Error: Unknown launch type: $LAUNCH_TYPE"
            exit 1
            ;;
    esac
    
    echo "Launching: $LAUNCH_CMD"
    eval "$LAUNCH_CMD"
}

main "$@"
LAUNCHER_EOF

chmod +x "$OUTPUT_SCRIPT"

# Now substitute actual values
sed -i "s|__LAUNCH_TYPE__|$LAUNCH_TYPE|g" "$OUTPUT_SCRIPT"
sed -i "s|__LAUNCH_TARGET__|$LAUNCH_TARGET|g" "$OUTPUT_SCRIPT"
sed -i "s|__LAUNCH_ARGS__|${LAUNCH_ARGS//&/\\&}|g" "$OUTPUT_SCRIPT"
sed -i "s|__DEPENDENCIES__|$DEPENDENCIES|g" "$OUTPUT_SCRIPT"

echo "✓ Launcher script generated: $OUTPUT_SCRIPT"
echo "  Launch type: $LAUNCH_TYPE"
echo "  Target: $LAUNCH_TARGET"
echo "  Dependencies: ${DEPENDENCIES:-none}"
