# Petty Cash Sorter - Production Ready

## 🚀 Overview

The Petty Cash Sorter is a comprehensive, production-ready system for processing petty cash transactions with advanced AI matching, real-time monitoring, and robust error handling.

## ✨ Key Features

### 🔧 **Core Functionality**
- **Automated Transaction Processing**: Downloads and processes petty cash transactions from Google Sheets
- **AI-Powered Rule Matching**: Intelligent matching of transactions to financial categories using enhanced AI algorithms
- **Database Management**: SQLite database for transaction tracking and audit trails
- **Google Sheets Integration**: Updates target financial sheets with matched amounts
- **Batch Processing**: Efficient processing of large transaction sets

### 🛡️ **Production Enhancements**
- **Configuration Management**: Centralized configuration with validation
- **API Rate Limiting**: Sophisticated rate limiting with token bucket algorithm
- **Real-time Monitoring**: Live dashboard with WebSocket updates
- **Comprehensive Testing**: Unit tests, integration tests, and performance tests
- **Error Recovery**: Exponential backoff and automatic retry mechanisms
- **Audit Trail**: Complete audit logging and reporting

## 📋 Requirements

### System Requirements
- **Python**: 3.8 or higher
- **Memory**: Minimum 512MB available RAM
- **Disk Space**: Minimum 100MB free space
- **Network**: Internet connection for Google Sheets API

### Required Files
- `config/service_account.json` - Google API credentials
- `JGD Truth Current.xlsx` - Rule definitions file
- `config/system_config.json` - System configuration

## 🚀 Quick Start

### 1. Installation

```bash
# Clone or download the project
cd PettyCash

# Install dependencies
pip install -r requirements.txt

# Verify installation
python run_tests.py
```

### 2. Configuration

The system uses a centralized configuration file at `config/system_config.json`. Key configuration sections:

```json
{
  "system": {
    "name": "Petty Cash Sorter - Final Comprehensive",
    "version": "2.0.0",
    "environment": "production"
  },
  "google_sheets": {
    "petty_cash_url": "https://docs.google.com/spreadsheets/d/...",
    "service_account_file": "config/service_account.json"
  },
  "processing": {
    "batch_size": 100,
    "min_confidence": 5,
    "max_confidence": 10
  },
  "api_rate_limiting": {
    "enabled": true,
    "requests_per_minute": 60,
    "burst_limit": 10
  },
  "monitoring": {
    "real_time_dashboard": {
      "enabled": true,
      "port": 5000,
      "host": "localhost"
    }
  }
}
```

### 3. Production Launch

```bash
# Run production launcher with full validation
python run_production.py
```

### 4. Real-time Monitoring

If enabled, access the real-time dashboard at:
```
http://localhost:5000
```

## 🧪 Testing

### Run All Tests
```bash
python run_tests.py
```

### Test Categories
- **Unit Tests**: Individual component testing
- **Integration Tests**: Component interaction testing
- **Performance Tests**: Performance benchmarking
- **System Validation**: Environment and configuration validation

## 📊 Monitoring and Reporting

### Real-time Dashboard
- **System Status**: Live health monitoring
- **Performance Metrics**: Processing rates and memory usage
- **Transaction Statistics**: Success rates and processing counts
- **API Rate Limiting**: Request statistics and limits
- **Activity Log**: Real-time log feed

### Generated Reports
- **Comprehensive Reports**: Detailed processing summaries
- **Audit Trails**: Complete transaction audit logs
- **Performance Analysis**: System performance metrics
- **Error Reports**: Failed transaction analysis

## 🔧 Configuration Management

### Configuration Validation
The system automatically validates:
- Required files existence
- Directory structure
- Database connectivity
- Google Sheets access
- API credentials

### Environment Validation
```bash
python config_manager.py
```

## 🛡️ API Rate Limiting

### Features
- **Token Bucket Algorithm**: Efficient rate limiting
- **Burst Handling**: Configurable burst limits
- **Cooldown Periods**: Automatic cooldown on failures
- **Per-Endpoint Limits**: Different limits for different operations

### Configuration
```json
{
  "api_rate_limiting": {
    "enabled": true,
    "requests_per_minute": 60,
    "burst_limit": 10,
    "cooldown_period_seconds": 60
  }
}
```

## 📁 File Structure

```
PettyCash/
├── config/
│   ├── system_config.json          # Main configuration
│   ├── service_account.json        # Google API credentials
│   └── layout_map_cache.json       # Cached layout mappings
├── logs/                           # Log files
├── data/                           # Data storage
├── reports/                        # Generated reports
├── tests/                          # Test suite
│   └── test_petty_cash_sorter.py   # Comprehensive tests
├── petty_cash_sorter_final_comprehensive.py  # Main application
├── config_manager.py               # Configuration management
├── api_rate_limiter.py             # API rate limiting
├── real_time_monitor.py            # Real-time monitoring
├── run_production.py               # Production launcher
├── run_tests.py                    # Test runner
└── requirements.txt                # Dependencies
```

## 🔍 Troubleshooting

### Common Issues

#### 1. Configuration Errors
```bash
# Validate configuration
python config_manager.py
```

#### 2. Missing Dependencies
```bash
# Install missing packages
pip install -r requirements.txt
```

#### 3. Google Sheets Access
- Verify `service_account.json` is valid
- Check Google Sheets permissions
- Ensure spreadsheet URLs are correct

#### 4. Database Issues
- Check disk space
- Verify database file permissions
- Review database logs in `logs/` directory

### Log Files
- `logs/petty_cash_sorter_final.log` - Main application logs
- `logs/api_rate_limiter.log` - Rate limiting logs
- `logs/audit_and_reporting.log` - Audit trail logs
- `logs/progress_monitor.log` - Progress monitoring logs

## 📈 Performance Optimization

### Batch Processing
- Adjust `batch_size` in configuration for optimal performance
- Monitor memory usage during large batch processing
- Use real-time monitoring to track processing rates

### API Rate Limiting
- Configure appropriate rate limits for your Google Sheets quota
- Monitor rate limiting statistics in the dashboard
- Adjust burst limits based on processing requirements

### Memory Management
- System automatically monitors memory usage
- Large transaction sets are processed in batches
- Memory usage is logged and reported

## 🔒 Security

### Credentials Management
- Service account credentials stored in `config/service_account.json`
- Credentials are not logged or exposed in reports
- Secure credential validation on startup

### Data Protection
- All sensitive data is validated and sanitized
- Audit trails track all data access and modifications
- Failed operations are logged for security review

## 📞 Support

### System Health Monitoring
The system provides comprehensive health monitoring:
- **Health Score**: 0-100 scale based on system status
- **Issue Detection**: Automatic detection of system problems
- **Performance Metrics**: Real-time performance tracking

### Error Recovery
- **Automatic Retries**: Failed operations are automatically retried
- **Exponential Backoff**: Intelligent retry timing
- **Error Classification**: Different error types handled appropriately

## 🎯 Production Checklist

Before deploying to production:

- [ ] All tests pass (`python run_tests.py`)
- [ ] Configuration validated (`python config_manager.py`)
- [ ] Google Sheets access verified
- [ ] Database created and accessible
- [ ] Log directories created
- [ ] Rate limiting configured appropriately
- [ ] Real-time monitoring enabled (optional)
- [ ] Backup procedures in place
- [ ] Error monitoring configured

## 📝 Changelog

### Version 2.0.0 (Production Ready)
- ✅ Added comprehensive configuration management
- ✅ Implemented sophisticated API rate limiting
- ✅ Added real-time monitoring dashboard
- ✅ Created comprehensive test suite
- ✅ Enhanced error recovery and logging
- ✅ Improved performance monitoring
- ✅ Added production launch script
- ✅ Centralized all configuration
- ✅ Added startup validation
- ✅ Enhanced security and audit trails

### Previous Versions
- Version 1.x: Basic functionality and core features

## 📄 License

This project is for internal use. All rights reserved.

---

**🚀 Ready for Production Deployment!**

The Petty Cash Sorter is now production-ready with comprehensive monitoring, testing, and error handling. Follow the quick start guide to get up and running quickly. 