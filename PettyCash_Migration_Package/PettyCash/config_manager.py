#!/usr/bin/env python3
"""
Configuration Manager for Petty Cash Sorter
Centralized configuration loading and validation
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

class ConfigManager:
    """Manages system configuration with validation and defaults."""
    
    def __init__(self, config_file: str = "config/system_config.json"):
        self.config_file = Path(config_file)
        self.config = {}
        self._load_config()
        self._validate_config()
    
    def _load_config(self):
        """Load configuration from JSON file."""
        try:
            if not self.config_file.exists():
                logging.error(f"Configuration file not found: {self.config_file}")
                raise FileNotFoundError(f"Configuration file not found: {self.config_file}")
            
            with open(self.config_file, 'r') as f:
                self.config = json.load(f)
            
            logging.info(f"Configuration loaded from {self.config_file}")
            
        except Exception as e:
            logging.error(f"Error loading configuration: {e}")
            raise
    
    def _validate_config(self):
        """Validate configuration and create required directories."""
        try:
            # Validate required sections
            required_sections = [
                'system', 'google_sheets', 'database', 'processing', 
                'ai_matching', 'api_rate_limiting', 'monitoring', 
                'files', 'directories', 'filing_system', 'layout_mapping'
            ]
            
            for section in required_sections:
                if section not in self.config:
                    raise ValueError(f"Missing required configuration section: {section}")
            
            # Create required directories
            for dir_name, dir_path in self.config['directories'].items():
                Path(dir_path).mkdir(parents=True, exist_ok=True)
                logging.debug(f"Ensured directory exists: {dir_path}")
            
            # Validate required files
            self._validate_required_files()
            
            logging.info("Configuration validation completed successfully")
            
        except Exception as e:
            logging.error(f"Configuration validation failed: {e}")
            raise
    
    def _validate_required_files(self):
        """Validate that required files exist."""
        required_files = [
            self.config['google_sheets']['service_account_file']
            # Note: JGD Truth file is no longer required as rules are stored in database
        ]
        
        missing_files = []
        for file_path in required_files:
            if not Path(file_path).exists():
                missing_files.append(file_path)
        
        if missing_files:
            raise FileNotFoundError(f"Required files missing: {missing_files}")
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """Get configuration value using dot notation (e.g., 'google_sheets.petty_cash_url')."""
        try:
            keys = key_path.split('.')
            value = self.config
            
            for key in keys:
                value = value[key]
            
            return value
        except (KeyError, TypeError):
            return default
    
    def get_section(self, section: str) -> Dict:
        """Get entire configuration section."""
        return self.config.get(section, {})
    
    def validate_startup_requirements(self) -> Dict:
        """Validate all startup requirements and return status."""
        validation_results = {
            'overall_status': 'PASS',
            'checks': {},
            'errors': [],
            'warnings': []
        }
        
        try:
            # Check configuration file
            validation_results['checks']['config_file'] = {
                'status': 'PASS',
                'message': f"Configuration file found: {self.config_file}"
            }
            
            # Check service account file
            service_account_file = self.config['google_sheets']['service_account_file']
            if Path(service_account_file).exists():
                validation_results['checks']['service_account'] = {
                    'status': 'PASS',
                    'message': f"Service account file found: {service_account_file}"
                }
            else:
                validation_results['checks']['service_account'] = {
                    'status': 'FAIL',
                    'message': f"Service account file missing: {service_account_file}"
                }
                validation_results['errors'].append(f"Service account file missing: {service_account_file}")
                validation_results['overall_status'] = 'FAIL'
            
            # Check JGD Truth file (optional - for reference only)
            jgd_truth_file = self.config['files'].get('jgd_truth_file')
            if jgd_truth_file and Path(jgd_truth_file).exists():
                validation_results['checks']['jgd_truth_file'] = {
                    'status': 'PASS',
                    'message': f"JGD Truth file found: {jgd_truth_file}"
                }
            elif jgd_truth_file:
                validation_results['checks']['jgd_truth_file'] = {
                    'status': 'INFO',
                    'message': f"JGD Truth file not found (rules now stored in database): {jgd_truth_file}"
                }
            
            # Check directories
            for dir_name, dir_path in self.config['directories'].items():
                dir_obj = Path(dir_path)
                if dir_obj.exists() and dir_obj.is_dir():
                    validation_results['checks'][f'directory_{dir_name}'] = {
                        'status': 'PASS',
                        'message': f"Directory exists: {dir_path}"
                    }
                else:
                    validation_results['checks'][f'directory_{dir_name}'] = {
                        'status': 'WARNING',
                        'message': f"Directory will be created: {dir_path}"
                    }
                    validation_results['warnings'].append(f"Directory will be created: {dir_path}")
            
            # Check database file
            db_path = self.config['database']['path']
            db_obj = Path(db_path)
            if db_obj.exists():
                validation_results['checks']['database'] = {
                    'status': 'PASS',
                    'message': f"Database file exists: {db_path}"
                }
            else:
                validation_results['checks']['database'] = {
                    'status': 'INFO',
                    'message': f"Database will be created: {db_path}"
                }
            
            logging.info(f"Startup validation completed: {validation_results['overall_status']}")
            
        except Exception as e:
            validation_results['overall_status'] = 'FAIL'
            validation_results['errors'].append(f"Validation error: {str(e)}")
            logging.error(f"Startup validation failed: {e}")
        
        return validation_results
    
    def print_validation_report(self, validation_results: Dict):
        """Print a formatted validation report."""
        print("\n" + "="*60)
        print("SYSTEM STARTUP VALIDATION REPORT")
        print("="*60)
        
        print(f"\nOverall Status: {validation_results['overall_status']}")
        
        if validation_results['errors']:
            print(f"\n❌ ERRORS ({len(validation_results['errors'])}):")
            for error in validation_results['errors']:
                print(f"  • {error}")
        
        if validation_results['warnings']:
            print(f"\n⚠️  WARNINGS ({len(validation_results['warnings'])}):")
            for warning in validation_results['warnings']:
                print(f"  • {warning}")
        
        print(f"\n📋 DETAILED CHECKS:")
        for check_name, check_result in validation_results['checks'].items():
            status_icon = {
                'PASS': '✅',
                'FAIL': '❌',
                'WARNING': '⚠️',
                'INFO': 'ℹ️'
            }.get(check_result['status'], '❓')
            
            print(f"  {status_icon} {check_name}: {check_result['message']}")
        
        print("="*60 + "\n")

def main():
    """Test configuration manager."""
    try:
        config_manager = ConfigManager()
        
        # Test configuration access
        print("Testing configuration access:")
        print(f"System name: {config_manager.get('system.name')}")
        print(f"Batch size: {config_manager.get('processing.batch_size')}")
        print(f"Petty cash URL: {config_manager.get('google_sheets.petty_cash_url')}")
        
        # Run validation
        validation_results = config_manager.validate_startup_requirements()
        config_manager.print_validation_report(validation_results)
        
        if validation_results['overall_status'] == 'PASS':
            print("✅ System is ready for startup!")
        else:
            print("❌ System has validation issues that need to be resolved.")
            
    except Exception as e:
        print(f"❌ Configuration manager test failed: {e}")

if __name__ == "__main__":
    main() 