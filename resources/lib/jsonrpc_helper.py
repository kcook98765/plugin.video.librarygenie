
import xbmc
import json

class JsonRpcHelper:
    @staticmethod
    def get_movies(start=0, limit=50, properties=None):
        if properties is None:
            properties = ["title", "year", "file", "imdbnumber", "uniqueid"]
            
        request = {
            "jsonrpc": "2.0",
            "method": "VideoLibrary.GetMovies",
            "params": {
                "properties": properties,
                "limits": {"start": start, "end": start + limit}
            },
            "id": 1
        }
        
        response = xbmc.executeJSONRPC(json.dumps(request))
        return json.loads(response)
