#!/bin/bash
# GitHub Token Setup Script for Linux/Unix
# This script helps you set up and verify your GitHub Personal Access Token

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
GRAY='\033[0;37m'
NC='\033[0m' # No Color

echo -e ""
echo -e "${CYAN}===========================================${NC}"
echo -e "${CYAN}   GitHub Token Setup for Linux/Unix${NC}"
echo -e "${CYAN}===========================================${NC}"
echo -e ""

# Check if GITHUB_TOKEN is already set
if [ -n "$GITHUB_TOKEN" ]; then
    masked_token="${GITHUB_TOKEN:0:8}..."
    echo -e "${GREEN}✅ GITHUB_TOKEN is already set in this session${NC}"
    echo -e "${YELLOW}Current token: $masked_token${NC}"
    echo -e ""
    echo -e "${CYAN}To verify it works, run:${NC}"
    echo -e "${GRAY}  python3 check_github_token.py${NC}"
    echo -e ""
    
    # Offer to test the token
    read -p "Would you like to test the token now? (y/n): " test_choice
    if [[ "$test_choice" =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}Testing GitHub token...${NC}"
        if command -v python3 &> /dev/null; then
            python3 check_github_token.py
        elif command -v python &> /dev/null; then
            python check_github_token.py
        else
            echo -e "${RED}❌ Python not found. Please install Python 3.${NC}"
            exit 1
        fi
    fi
    exit 0
fi

echo -e "${RED}❌ GITHUB_TOKEN environment variable is not set${NC}"
echo -e ""
echo -e "${CYAN}📋 To set up your GitHub token:${NC}"
echo -e ""
echo -e "${GRAY}1. 🌐 Go to: https://github.com/settings/tokens${NC}"
echo -e "${GRAY}2. 🆕 Click 'Generate new token' -> 'Generate new token (classic)'${NC}"
echo -e "${GRAY}3. 📝 Give it a name like 'Rust Crate Pipeline'${NC}"
echo -e "${GRAY}4. ⏰ Set expiration (recommend 90 days or 1 year)${NC}"
echo -e "${GRAY}5. ✅ Select these scopes:${NC}"
echo -e "${GRAY}   - public_repo (for public repository access)${NC}"
echo -e "${GRAY}   - read:user (for user information)${NC}"
echo -e ""

read -p "Do you have your GitHub token ready? (y/n): " setup_choice

if [[ "$setup_choice" =~ ^[Yy]$ ]]; then
    echo -e ""
    echo -e "${YELLOW}Enter your GitHub token (input will be hidden):${NC}"
    read -s token
    echo -e ""
    
    if [ ${#token} -lt 20 ]; then
        echo -e "${YELLOW}⚠️  Token seems too short. GitHub tokens are usually 40+ characters.${NC}"
        read -p "Continue anyway? (y/n): " continue_choice
        if [[ ! "$continue_choice" =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
    
    echo -e ""
    echo -e "${CYAN}Choose how to set the token:${NC}"
    echo -e "${GRAY}1. This session only (temporary)${NC}"
    echo -e "${GRAY}2. Permanently in ~/.bashrc${NC}"
    echo -e "${GRAY}3. Permanently in ~/.zshrc${NC}"
    echo -e "${GRAY}4. Permanently in ~/.profile${NC}"
    echo -e ""
    
    read -p "Enter choice (1-4): " choice
    
    case $choice in
        1)
            export GITHUB_TOKEN="$token"
            echo -e "${GREEN}✅ GITHUB_TOKEN set for this session${NC}"
            echo -e "${YELLOW}Note: You'll need to set it again when you open a new terminal${NC}"
            ;;
        2)
            echo "export GITHUB_TOKEN=\"$token\"" >> ~/.bashrc
            export GITHUB_TOKEN="$token"
            echo -e "${GREEN}✅ GITHUB_TOKEN added to ~/.bashrc${NC}"
            echo -e "${GREEN}✅ Also set for this current session${NC}"
            echo -e "${YELLOW}Note: Run 'source ~/.bashrc' or open a new terminal for permanent effect${NC}"
            ;;
        3)
            echo "export GITHUB_TOKEN=\"$token\"" >> ~/.zshrc
            export GITHUB_TOKEN="$token"
            echo -e "${GREEN}✅ GITHUB_TOKEN added to ~/.zshrc${NC}"
            echo -e "${GREEN}✅ Also set for this current session${NC}"
            echo -e "${YELLOW}Note: Run 'source ~/.zshrc' or open a new terminal for permanent effect${NC}"
            ;;
        4)
            echo "export GITHUB_TOKEN=\"$token\"" >> ~/.profile
            export GITHUB_TOKEN="$token"
            echo -e "${GREEN}✅ GITHUB_TOKEN added to ~/.profile${NC}"
            echo -e "${GREEN}✅ Also set for this current session${NC}"
            echo -e "${YELLOW}Note: Run 'source ~/.profile' or open a new terminal for permanent effect${NC}"
            ;;
        *)
            echo -e "${RED}❌ Invalid choice. Setting for this session only.${NC}"
            export GITHUB_TOKEN="$token"
            ;;
    esac
    
    echo -e ""
    echo -e "${YELLOW}🧪 Testing the token...${NC}"
    if command -v python3 &> /dev/null; then
        python3 check_github_token.py
    elif command -v python &> /dev/null; then
        python check_github_token.py
    else
        echo -e "${RED}❌ Python not found. Please install Python 3.${NC}"
        echo -e "${GRAY}On Ubuntu/Debian: sudo apt install python3${NC}"
        echo -e "${GRAY}On CentOS/RHEL: sudo yum install python3${NC}"
        echo -e "${GRAY}On Arch: sudo pacman -S python${NC}"
        exit 1
    fi
    
else
    echo -e ""
    echo -e "${CYAN}📋 Manual Setup Instructions:${NC}"
    echo -e ""
    echo -e "${GRAY}METHOD 1 - Temporary (this session only):${NC}"
    echo -e "${GRAY}  export GITHUB_TOKEN=\"your_token_here\"${NC}"
    echo -e ""
    echo -e "${GRAY}METHOD 2 - Permanent (add to your shell config):${NC}"
    echo -e "${GRAY}  echo 'export GITHUB_TOKEN=\"your_token_here\"' >> ~/.bashrc${NC}"
    echo -e "${GRAY}  source ~/.bashrc${NC}"
    echo -e ""
    echo -e "${GRAY}For Zsh users:${NC}"
    echo -e "${GRAY}  echo 'export GITHUB_TOKEN=\"your_token_here\"' >> ~/.zshrc${NC}"
    echo -e "${GRAY}  source ~/.zshrc${NC}"
    echo -e ""
    echo -e "${CYAN}After setting the token, verify it works:${NC}"
    echo -e "${GRAY}  python3 check_github_token.py${NC}"
    echo -e ""
fi

echo -e "${GRAY}Press any key to continue...${NC}"
read -n 1 -s
