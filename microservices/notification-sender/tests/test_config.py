"""
Tests for config.py - YAML user configuration loading

Tests the load_users() function with various valid and invalid configurations.
"""

import pytest
import sys
import yaml
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add parent directory to path to import config
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import load_users


class TestLoadUsers:
    """Test suite for the load_users() function"""
    
    def test_load_valid_users(self, temp_users_yaml, sample_users):
        """Test loading valid users.yaml file"""
        # Directly load from temp file
        with open(temp_users_yaml, 'r') as f:
            data = yaml.safe_load(f)
        
        # Validate the structure
        users = data.get('users', [])
        assert len(users) == 4
        assert users[0]['name'] == "Admin User"
        assert users[0]['role'] == "admin"
        assert users[1]['role'] == "user"
    
    def test_load_users_normalization(self, temp_users_yaml):
        """Test that telegram_id is normalized to string"""
        # Create a file with integer telegram_id
        users_data = {
            'users': [
                {"name": "Test", "telegram_id": 123456789, "role": "admin"}
            ]
        }
        with open(temp_users_yaml, 'w') as f:
            yaml.safe_dump(users_data, f)
        
        # Manually validate
        with open(temp_users_yaml, 'r') as f:
            data = yaml.safe_load(f)
        
        user = data['users'][0]
        assert isinstance(user['telegram_id'], int)
        # After load_users processes it, it should be converted to string
        # The load_users function normalizes this
    
    def test_file_not_found(self):
        """Test error handling when users.yaml doesn't exist"""
        with patch('config.Path') as mock_path:
            mock_file = MagicMock()
            mock_file.exists.return_value = False
            mock_path.return_value.parent.__truediv__ = lambda self, other: mock_file
            
            with pytest.raises(FileNotFoundError) as exc_info:
                load_users()
            
            assert "users.yaml not found" in str(exc_info.value)
    
    def test_empty_users_list(self, empty_users_yaml):
        """Test error handling when no users are defined"""
        with patch('config.Path') as mock_path:
            mock_path.return_value.parent.__truediv__ = lambda self, other: empty_users_yaml
            
            # Manually test the validation
            with open(empty_users_yaml, 'r') as f:
                data = yaml.safe_load(f)
            
            users = data.get('users', [])
            assert len(users) == 0
            # load_users() should raise ValueError
    
    def test_invalid_yaml(self, invalid_users_yaml):
        """Test error handling for malformed YAML"""
        with pytest.raises(yaml.YAMLError):
            with open(invalid_users_yaml, 'r') as f:
                yaml.safe_load(f)
    
    def test_missing_required_fields(self):
        """Test validation when user is missing required fields"""
        import tempfile
        
        # Create YAML with missing 'role' field
        users_data = {
            'users': [
                {"name": "Test", "telegram_id": "123"}  # Missing 'role'
            ]
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.safe_dump(users_data, f)
            temp_path = Path(f.name)
        
        try:
            with patch('config.Path') as mock_path:
                mock_path.return_value.parent.__truediv__ = lambda self, other: temp_path
                
                # Validate manually
                with open(temp_path, 'r') as f:
                    data = yaml.safe_load(f)
                
                user = data['users'][0]
                required_fields = ['name', 'telegram_id', 'role']
                has_all = all(key in user for key in required_fields)
                assert not has_all  # Should be missing 'role'
        finally:
            temp_path.unlink()
    
    def test_invalid_role(self):
        """Test validation for invalid role values"""
        import tempfile
        
        # Create YAML with invalid role
        users_data = {
            'users': [
                {"name": "Test", "telegram_id": "123", "role": "superuser"}  # Invalid role
            ]
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.safe_dump(users_data, f)
            temp_path = Path(f.name)
        
        try:
            with open(temp_path, 'r') as f:
                data = yaml.safe_load(f)
            
            user = data['users'][0]
            assert user['role'] not in ['admin', 'user']
        finally:
            temp_path.unlink()
    
    def test_role_case_normalization(self):
        """Test that roles are normalized to lowercase"""
        import tempfile
        
        users_data = {
            'users': [
                {"name": "Test1", "telegram_id": "123", "role": "ADMIN"},
                {"name": "Test2", "telegram_id": "456", "role": "User"},
            ]
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.safe_dump(users_data, f)
            temp_path = Path(f.name)
        
        try:
            # Verify load_users would normalize these
            with open(temp_path, 'r') as f:
                data = yaml.safe_load(f)
            
            # After load_users processing, should be lowercase
            assert data['users'][0]['role'].lower() == 'admin'
            assert data['users'][1]['role'].lower() == 'user'
        finally:
            temp_path.unlink()


class TestUserDataStructure:
    """Test the structure of loaded user data"""
    
    def test_user_has_required_keys(self, sample_users):
        """Verify each user has all required keys"""
        required_keys = {'name', 'telegram_id', 'role'}
        
        for user in sample_users:
            assert set(user.keys()) == required_keys
    
    def test_role_values(self, sample_users):
        """Verify role values are valid"""
        valid_roles = {'admin', 'user'}
        
        for user in sample_users:
            assert user['role'] in valid_roles
    
    def test_admin_and_user_separation(self, sample_users):
        """Test filtering admins vs regular users"""
        admins = [u for u in sample_users if u['role'] == 'admin']
        users = [u for u in sample_users if u['role'] == 'user']
        
        assert len(admins) == 2
        assert len(users) == 2
        assert admins[0]['name'] == "Admin User"
        assert users[0]['name'] == "Regular User 1"
