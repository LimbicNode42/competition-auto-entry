#!/usr/bin/env python3
"""
MCP Server Setup and Integration Script
Installs and configures MCP servers for browser automation and computer vision
"""

import json
import subprocess
import sys
import os
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MCPServerSetup:
    """Setup and configure MCP servers for competition entry automation"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent
        self.mcp_config_path = self.project_root / "mcp_config.json"
    
    def install_mcp_servers(self):
        """Install recommended MCP servers for competition entry"""
        
        mcp_servers = {
            # Browser automation servers
            "playwright-mcp": {
                "npm_package": "@microsoft/playwright-mcp",
                "description": "Official Microsoft Playwright MCP server",
                "capabilities": ["browser_automation", "accessibility_tree", "form_interaction"]
            },
            
            "browser-use-mcp": {
                "git_repo": "https://github.com/co-browser/browser-use-mcp-server",
                "description": "Advanced browser automation with computer vision",
                "capabilities": ["ai_browser_control", "vnc_server", "visual_feedback"]
            },
            
            "screenshot-mcp": {
                "git_repo": "https://github.com/just-every/mcp-screenshot-website-fast",
                "description": "Fast screenshot capture optimized for Claude Vision",
                "capabilities": ["screenshot_capture", "page_tiling", "claude_vision_integration"]
            },
            
            "image-analysis-mcp": {
                "git_repo": "https://github.com/sunriseapps/imagesorcery-mcp",
                "description": "Computer vision-based image recognition tools",
                "capabilities": ["image_recognition", "form_detection", "visual_analysis"]
            },
            
            # Additional computer vision and automation servers
            "screen-pilot-mcp": {
                "git_repo": "https://github.com/Mtehabsim/ScreenPilot",
                "description": "AI-powered screen control and GUI interaction",
                "capabilities": ["screen_control", "mouse_keyboard_automation", "gui_detection"]
            },
            
            "omniparser-autogui-mcp": {
                "git_repo": "https://github.com/NON906/omniparser-autogui-mcp",
                "description": "Automatic GUI operation with advanced parsing",
                "capabilities": ["gui_automation", "element_detection", "smart_interaction"]
            },
            
            "mobile-mcp": {
                "git_repo": "https://github.com/mobile-next/mobile-mcp",
                "description": "Mobile device automation and app scraping",
                "capabilities": ["mobile_automation", "app_interaction", "device_control"]
            },
            
            "agentql-mcp": {
                "git_repo": "https://github.com/tinyfish-io/agentql-mcp",
                "description": "Advanced data extraction with AI-powered querying",
                "capabilities": ["data_extraction", "semantic_querying", "web_scraping"]
            },
            
            "webscraping-ai-mcp": {
                "git_repo": "https://github.com/webscraping-ai/webscraping-ai-mcp-server",
                "description": "Professional web scraping with AI assistance",
                "capabilities": ["intelligent_scraping", "anti_detection", "structured_extraction"]
            }
        }
        
        logger.info("Installing MCP servers for competition entry automation...")
        
        installed_servers = {}
        
        for server_name, config in mcp_servers.items():
            try:
                logger.info(f"Installing {server_name}: {config['description']}")
                
                if "npm_package" in config:
                    # Install via npm
                    result = subprocess.run([
                        "npm", "install", "-g", config["npm_package"]
                    ], capture_output=True, text=True)
                    
                    if result.returncode == 0:
                        installed_servers[server_name] = {
                            **config,
                            "installed": True,
                            "install_method": "npm",
                            "command": config["npm_package"]
                        }
                        logger.info(f"✅ Successfully installed {server_name}")
                    else:
                        logger.error(f"❌ Failed to install {server_name}: {result.stderr}")
                        installed_servers[server_name] = {**config, "installed": False, "error": result.stderr}
                
                elif "git_repo" in config:
                    # Clone and setup git repository
                    server_dir = self.project_root / "mcp_servers" / server_name
                    server_dir.parent.mkdir(exist_ok=True)
                    
                    if not server_dir.exists():
                        result = subprocess.run([
                            "git", "clone", config["git_repo"], str(server_dir)
                        ], capture_output=True, text=True)
                        
                        if result.returncode == 0:
                            # Try to install dependencies if package.json exists
                            if (server_dir / "package.json").exists():
                                subprocess.run(["npm", "install"], cwd=server_dir)
                            elif (server_dir / "requirements.txt").exists():
                                subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], cwd=server_dir)
                            
                            installed_servers[server_name] = {
                                **config,
                                "installed": True,
                                "install_method": "git",
                                "path": str(server_dir)
                            }
                            logger.info(f"✅ Successfully cloned and setup {server_name}")
                        else:
                            logger.error(f"❌ Failed to clone {server_name}: {result.stderr}")
                            installed_servers[server_name] = {**config, "installed": False, "error": result.stderr}
                    else:
                        logger.info(f"📂 {server_name} already exists, skipping clone")
                        installed_servers[server_name] = {
                            **config,
                            "installed": True,
                            "install_method": "git",
                            "path": str(server_dir)
                        }
                
            except Exception as e:
                logger.error(f"❌ Error installing {server_name}: {e}")
                installed_servers[server_name] = {**config, "installed": False, "error": str(e)}
        
        # Save installation results
        with open(self.mcp_config_path, 'w') as f:
            json.dump(installed_servers, f, indent=2)
        
        logger.info(f"MCP server installation complete. Config saved to {self.mcp_config_path}")
        return installed_servers
    
    def create_claude_desktop_config(self):
        """Create Claude Desktop configuration for MCP servers"""
        
        # Claude Desktop config path varies by OS
        if sys.platform == "win32":
            claude_config_dir = Path.home() / "AppData" / "Roaming" / "Claude"
        elif sys.platform == "darwin":
            claude_config_dir = Path.home() / "Library" / "Application Support" / "Claude"
        else:
            claude_config_dir = Path.home() / ".config" / "claude"
        
        claude_config_dir.mkdir(parents=True, exist_ok=True)
        claude_config_path = claude_config_dir / "claude_desktop_config.json"
        
        # Load existing config or create new
        if claude_config_path.exists():
            with open(claude_config_path, 'r') as f:
                claude_config = json.load(f)
        else:
            claude_config = {"mcpServers": {}}
        
        # Load our MCP server config
        if self.mcp_config_path.exists():
            with open(self.mcp_config_path, 'r') as f:
                mcp_servers = json.load(f)
        else:
            logger.warning("No MCP server config found. Run install_mcp_servers() first.")
            return
        
        # Add our servers to Claude config
        for server_name, config in mcp_servers.items():
            if config.get("installed", False):
                if config.get("install_method") == "npm":
                    claude_config["mcpServers"][f"competition-{server_name}"] = {
                        "command": "npx",
                        "args": [config["command"]],
                        "env": {}
                    }
                elif config.get("install_method") == "git" and "path" in config:
                    server_path = Path(config["path"])
                    
                    # Look for the main executable
                    if (server_path / "dist" / "index.js").exists():
                        claude_config["mcpServers"][f"competition-{server_name}"] = {
                            "command": "node",
                            "args": [str(server_path / "dist" / "index.js")],
                            "env": {}
                        }
                    elif (server_path / "index.js").exists():
                        claude_config["mcpServers"][f"competition-{server_name}"] = {
                            "command": "node",
                            "args": [str(server_path / "index.js")],
                            "env": {}
                        }
                    elif (server_path / "main.py").exists():
                        claude_config["mcpServers"][f"competition-{server_name}"] = {
                            "command": sys.executable,
                            "args": [str(server_path / "main.py")],
                            "env": {}
                        }
        
        # Save Claude config
        with open(claude_config_path, 'w') as f:
            json.dump(claude_config, f, indent=2)
        
        logger.info(f"Claude Desktop config updated: {claude_config_path}")
        logger.info("Restart Claude Desktop to use the new MCP servers")
    
    def test_mcp_servers(self):
        """Test installed MCP servers"""
        logger.info("Testing MCP server installations...")
        
        if not self.mcp_config_path.exists():
            logger.error("No MCP servers configured. Run install_mcp_servers() first.")
            return
        
        with open(self.mcp_config_path, 'r') as f:
            mcp_servers = json.load(f)
        
        for server_name, config in mcp_servers.items():
            if config.get("installed", False):
                logger.info(f"Testing {server_name}...")
                
                # Basic connectivity test would go here
                # For now, just check if files exist
                if config.get("install_method") == "git" and "path" in config:
                    server_path = Path(config["path"])
                    if server_path.exists():
                        logger.info(f"✅ {server_name} files present at {server_path}")
                    else:
                        logger.error(f"❌ {server_name} files missing at {server_path}")
                else:
                    logger.info(f"✅ {server_name} installed via npm")
    
    def create_integration_example(self):
        """Create example script showing how to use MCP servers with competition entry"""
        
        example_script = '''#!/usr/bin/env python3
"""
Example: Using MCP Servers with Competition Entry System
This shows how to integrate MCP servers for enhanced automation
"""

import asyncio
import json
from pathlib import Path

class MCPIntegrationExample:
    """
    Example integration of MCP servers with competition entry
    """
    
    async def example_with_playwright_mcp(self):
        """
        Example using Microsoft Playwright MCP server
        """
        # In a real integration, you would:
        # 1. Connect to the Playwright MCP server
        # 2. Send structured commands for browser automation
        # 3. Receive accessibility tree data
        # 4. Use that data for intelligent form filling
        
        print("Example: Playwright MCP Integration")
        print("1. Connect to Playwright MCP server")
        print("2. Get accessibility tree for form analysis")
        print("3. Fill forms using structured data")
        print("4. Take screenshots for validation")
    
    async def example_with_vision_mcp(self):
        """
        Example using computer vision MCP servers
        """
        print("Example: Computer Vision MCP Integration")
        print("1. Take screenshot of competition page")
        print("2. Send to vision MCP server for analysis")
        print("3. Identify form fields and their types")
        print("4. Validate form completion with AI")
    
    async def run_examples(self):
        """Run all examples"""
        await self.example_with_playwright_mcp()
        print()
        await self.example_with_vision_mcp()

# To run this example:
# python mcp_integration_example.py

if __name__ == "__main__":
    example = MCPIntegrationExample()
    asyncio.run(example.run_examples())
'''
        
        example_path = self.project_root / "mcp_integration_example.py"
        with open(example_path, 'w') as f:
            f.write(example_script)
        
        logger.info(f"Created MCP integration example: {example_path}")
    
    def setup_development_environment(self):
        """Setup complete development environment for MCP integration"""
        logger.info("Setting up MCP development environment...")
        
        # Create directories
        (self.project_root / "mcp_servers").mkdir(exist_ok=True)
        (self.project_root / "screenshots").mkdir(exist_ok=True)
        (self.project_root / "logs").mkdir(exist_ok=True)
        
        # Install requirements
        logger.info("Installing Python requirements...")
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        
        # Install Playwright browsers
        logger.info("Installing Playwright browsers...")
        subprocess.run([sys.executable, "-m", "playwright", "install"])
        
        # Setup Tesseract OCR path (Windows)
        if sys.platform == "win32":
            tesseract_paths = [
                r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"
            ]
            
            for path in tesseract_paths:
                if Path(path).exists():
                    logger.info(f"Found Tesseract at: {path}")
                    # You might want to set this in environment or config
                    break
            else:
                logger.warning("Tesseract OCR not found. Please install from: https://github.com/UB-Mannheim/tesseract/wiki")
        
        logger.info("Development environment setup complete!")

def main():
    """Main setup function"""
    setup = MCPServerSetup()
    
    print("🚀 Competition Auto-Entry MCP Setup")
    print("===================================")
    
    choice = input("""
Choose setup option:
1. Full setup (install servers + configure Claude + examples)
2. Install MCP servers only
3. Configure Claude Desktop only
4. Create examples only
5. Setup development environment only

Enter choice (1-5): """).strip()
    
    if choice == "1" or choice == "":
        print("\n🔧 Running full setup...")
        setup.setup_development_environment()
        setup.install_mcp_servers()
        setup.create_claude_desktop_config()
        setup.create_integration_example()
        setup.test_mcp_servers()
        
    elif choice == "2":
        print("\n📦 Installing MCP servers...")
        setup.install_mcp_servers()
        setup.test_mcp_servers()
        
    elif choice == "3":
        print("\n⚙️  Configuring Claude Desktop...")
        setup.create_claude_desktop_config()
        
    elif choice == "4":
        print("\n📝 Creating examples...")
        setup.create_integration_example()
        
    elif choice == "5":
        print("\n🛠️  Setting up development environment...")
        setup.setup_development_environment()
    
    print("\n✅ Setup complete!")
    print("\nNext steps:")
    print("1. Edit config.json with your personal details")
    print("2. Add your Anthropic API key to enhanced_competition_entry.py")
    print("3. Restart Claude Desktop if you configured MCP servers")
    print("4. Run: python enhanced_competition_entry.py")

if __name__ == "__main__":
    main()
