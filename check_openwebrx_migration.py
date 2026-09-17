#!/usr/bin/env python3
"""
Wichita OpenWebRX+ Migration Tracker
Monitors and guides the migration process
"""

import subprocess
import os
import sys
from datetime import datetime, timezone

class OpenWebRXMigration:
    def __init__(self):
        self.checks = []
        self.project_root = "/Users/mattcarp/Documents/projects/rf-forensics-toolkit"
        
    def log(self, message, status="INFO"):
        symbols = {"PASS": "✅", "FAIL": "❌", "INFO": "ℹ️", "WARN": "⚠️"}
        print(f"{symbols.get(status, '•')} {message}")
        
    def check_command(self, cmd, name):
        """Check if a command exists"""
        try:
            result = subprocess.run(['which', cmd], capture_output=True)
            exists = result.returncode == 0
            self.checks.append((name, exists))
            return exists
        except:
            self.checks.append((name, False))
            return False
    
    def run_checks(self):
        print("="*60)
        print("🎯 WICHITA OPENWEBRX+ MIGRATION STATUS")
        print("="*60)
        print(f"📅 {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        # Phase 1: Prerequisites
        print("📦 PHASE 1: Prerequisites")
        print("-"*40)
        
        if self.check_command('python3', 'Python 3'):
            self.log("Python 3 installed", "PASS")
        else:
            self.log("Python 3 missing - run: brew install python3", "FAIL")
            
        if self.check_command('brew', 'Homebrew'):
            self.log("Homebrew installed", "PASS")
        else:
            self.log("Homebrew missing - install from brew.sh", "FAIL")
            
        if self.check_command('hackrf_info', 'HackRF tools'):
            self.log("HackRF tools installed", "PASS")
        else:
            self.log("HackRF tools installing... (brew install hackrf)", "WARN")
        
        # Phase 2: SDR Libraries
        print("\n📡 PHASE 2: SDR Libraries")
        print("-"*40)
        
        if self.check_command('csdr', 'CSDR'):
            self.log("CSDR installed", "PASS")
        else:
            self.log("CSDR missing - run: brew install csdr", "FAIL")
            
        if self.check_command('SoapySDRUtil', 'SoapySDR'):
            self.log("SoapySDR installed", "PASS")
            # Test HackRF detection
            try:
                result = subprocess.run(['SoapySDRUtil', '--probe=driver=hackrf'], 
                                      capture_output=True, text=True, timeout=5)
                if 'Found device' in result.stdout:
                    self.log("HackRF detected by SoapySDR!", "PASS")
                else:
                    self.log("HackRF not detected by SoapySDR", "WARN")
            except:
                pass
        else:
            self.log("SoapySDR missing - run: brew install soapysdr", "FAIL")
        
        # Phase 3: OpenWebRX+
        print("\n🌐 PHASE 3: OpenWebRX+ Installation")
        print("-"*40)
        
        owrx_path = os.path.join(self.project_root, "openwebrx")
        if os.path.exists(owrx_path):
            self.log("OpenWebRX+ repository cloned", "PASS")
            
            # Check for config
            config_file = os.path.join(owrx_path, "config_webrx.py")
            if os.path.exists(config_file):
                self.log("Configuration file exists", "PASS")
            else:
                self.log("Configuration needed - create config_webrx.py", "WARN")
        else:
            self.log("OpenWebRX+ not cloned yet", "FAIL")
            print("   Run: git clone https://github.com/jketterl/openwebrx.git")
        
        # Summary
        print("\n" + "="*60)
        print("📊 MIGRATION SUMMARY")
        print("="*60)
        
        passed = sum(1 for _, status in self.checks if status)
        total = len(self.checks)
        percentage = (passed / total * 100) if total > 0 else 0
        
        print(f"✅ Passed: {passed}/{total} ({percentage:.1f}%)")
        
        if percentage == 100:
            print("\n🎉 READY TO START OPENWEBRX+!")
            print("Run: cd openwebrx && python3 openwebrx.py")
        elif percentage >= 50:
            print("\n⚠️ PARTIALLY READY - Install missing components")
        else:
            print("\n❌ NOT READY - Complete installation steps above")
        
        # Next steps
        print("\n📋 NEXT STEPS:")
        if percentage < 100:
            print("1. Install missing components shown above")
            print("2. Run this script again to check progress")
        else:
            print("1. Start OpenWebRX+: cd openwebrx && python3 openwebrx.py")
            print("2. Open browser to http://localhost:8073")
            print("3. Configure for Malta frequencies")
        
        print("\n" + "="*60)
        print("From Malta, we protect the Mediterranean! 🇲🇹")
        print("="*60)

if __name__ == "__main__":
    migration = OpenWebRXMigration()
    migration.run_checks()