import yaml
import os

class ConfigManager:
    def __init__(self, config_file_path: str = None):
        """
        Initialize the ConfigManager with a path to the configuration file.
        
        :param config_file_path: Optional path to the YAML configuration file.
                                 If not provided, it will try to get the path from the
                                 CONFIG_FILE_PATH environment variable or default to 'random.yml'.
        """
        self.config_cache = {}
        if not config_file_path or not os.path.isfile(config_file_path):
            print(f"Warning: Configuration file {config_file_path} not found. Exiting")
            exit(1)
        self.config_file_path = config_file_path or os.getenv('CONFIG_FILE_PATH', '')
    
    def load_config(self) -> dict:
        """
        Load the configuration from a YAML file.
        
        :return: The loaded configuration as a dictionary.
        """
        if not self.config_cache:  # Load config only if it hasn't been loaded before
            try:
                with open(self.config_file_path, 'r') as file:
                    self.config_cache = yaml.safe_load(file) or {}
            except FileNotFoundError:
                print(f"Warning: Configuration file {self.config_file_path} not found.")
            except yaml.YAMLError as exc:
                print(f"Error parsing the YAML file: {exc}")
        return self.config_cache

    def read_config(self, key: str, default: str = "") -> str:
        """
        Read configuration values from the loaded YAML configuration.
        
        :param key: The configuration key. Supports 'nested.key' for nested dictionaries.
        :param default: The default value to return if the key is not found.
        :return: The configuration value.
        """
        config = self.load_config()
        try:
            for part in key.split('.'):
                config = config[part]
            return config
        except KeyError:
            return default
