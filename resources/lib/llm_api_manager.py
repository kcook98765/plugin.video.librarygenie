""" /resources/lib/llm_api_manager.py """
import urllib.request
import urllib.parse
import json
import re
import xbmcgui
from resources.lib import utils
from resources.lib.config_manager import Config

class LLMApiManager:

    def __init__(self):
        """
        Initializes the LLMApiManager with the provided API key from the Kodi addon settings.
        """
        config = Config()
        self.api_key = config.openai_api_key
        self.base_url = 'https://api.openai.com/v1/chat/completions'
        self.api_temperature = config.api_temperature
        self.api_max_tokens = 3000

    def extract_json_from_response(self, response_text):
        # Use regular expression to extract JSON data delimited by ```json ... ```
        match = re.search(r'```json\s+(.*?)\s+```', response_text, re.DOTALL)
        if match:
            return match.group(1)
        return ""

    def generate_query(self, input_data):
        system_message = "You are a helpful assistant."
        user_message = (
            f"Here is the user request, interpret this and build a json "
            f"response file containing movies list with title, year and director: "
            f"```{input_data}``` "
            f"Response should be a single JSON format"
        )

        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.api_key}'
        }
        data = {
            "model": "gpt-3.5-turbo",
            "messages": [
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_message}
            ],
            "max_tokens": self.api_max_tokens,
            "temperature": self.api_temperature
        }

        data_bytes = json.dumps(data).encode('utf-8')
        utils.log(f"Preparing API request with temperature: {self.api_temperature}", "DEBUG")
        utils.log(f"API request max tokens: {self.api_max_tokens}", "DEBUG")

        req = urllib.request.Request(self.base_url, data=data_bytes, headers=headers)
        self.log_request(req)

        busy_dialog = xbmcgui.DialogProgress()
        busy_dialog.create("LibraryGenie", "Processing request, please wait...")

        try:
            with urllib.request.urlopen(req) as response:
                response_body = response.read().decode('utf-8')
                response_data = json.loads(response_body)
                response_text = response_data['choices'][0]['message']['content']
                self.log_response(response_text)

                json_data = self.extract_json_from_response(response_text)
                parsed_data = json.loads(json_data)
                rpc = parsed_data.get('RPC', '')
                name = parsed_data.get('name', '')

                if rpc:
                    movies = self.execute_rpc_query(rpc)
                    return rpc, name, movies
                return rpc, name, []
        except urllib.request.HTTPError as e:
            utils.log(f"HTTP error: {e.code} {e.reason}", "ERROR")
        except json.JSONDecodeError as e:
            utils.log(f"JSON decode error: {e.msg}", "ERROR")
        except TypeError as e:
            utils.log(f"Type error: {e}", "ERROR")
        except ValueError as e:
            utils.log(f"Value error: {e}", "ERROR")
        except Exception as e:
            utils.log(f"Unexpected error: {e}", "ERROR")
            raise

        busy_dialog.close()
        return "", "", []

    def execute_rpc_query(self, rpc):
        try:
            from resources.lib.query_manager import QueryManager
            from resources.lib.config import Config
            
            query_manager = QueryManager(Config().db_path)
            results = query_manager.execute_rpc_query(rpc)
            
            utils.log(f"Query results length: {len(results)}", "DEBUG")
            return results

        except KeyError as e:
            utils.log(f"Key error in RPC query: {e}", "ERROR")
            return []
        except json.JSONDecodeError as e:
            utils.log(f"JSON decode error in RPC query: {e}", "ERROR")
            return []
        except TypeError as e:
            utils.log(f"Type error in RPC query: {e}", "ERROR")
            return []
        except Exception as e:  # pylint: disable=broad-except
            utils.log(f"Unexpected error in RPC query: {e}", "ERROR")
            xbmcgui.Dialog().notification("LibraryGenie", "Error executing RPC query", xbmcgui.NOTIFICATION_ERROR, 5000)
            return []


    def log_request(self, request):
        headers = request.headers.copy()
        if 'Authorization' in headers:
            headers['Authorization'] = '__REDACTED__'
        utils.log(f"Sending request to {request.full_url}", "INFO")
        utils.log(f"Headers: {headers}", "DEBUG")
        utils.log(f"Body: {request.data.decode('utf-8')}", "DEBUG")


    def log_response(self, response):
        utils.log(f"Response: {response}", "DEBUG")