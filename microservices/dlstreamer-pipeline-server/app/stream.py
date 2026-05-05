#from .logger import logger
import requests
import subprocess
import urllib.parse

class Stream:
    def __init__(self):
        self.stream_id = None
        self.stream_url = None
        self.stream_data = None  # Placeholder for stream data
        self.data = None  # Placeholder for additional stream data
        self.payload = None  # Placeholder for stream configuration payload
        self.metadata = None

    def add_stream(self, stream_path, model_path):
        self.payload = {
        "source":{
            "uri":f"file://{stream_path}",
            "type":"uri"
        },
        "destination":{
            "metadata":{
                "type":"file",
                "path":"/tmp/results.jsonl",
                "format":"json-lines"
            },
            "frame":{
                "type":"webrtc",
                "peer-id":"pallet-defect-detection"
            }
        },
        "parameters":{
            "detection-properties":{
                "model":f"{model_path}",
                "device":"CPU"
            }
        }
        }

        url = "http://dlstreamer-pipeline-server:8080/pipelines/user_defined_pipelines/pallet_defect_detection"
        response = requests.post(url, json=self.payload, headers={"Content-Type": "application/json"})
        response.raise_for_status()
        return response.text


    def view_metadata(self, file_path):
        file_path = urllib.parse.quote(file_path)
        url = f"http://dlstreamer-pipeline-server:8080/metadata/{file_path}"
        self.metadata = requests.get(url)
        return self.metadata.text
    
    def view_pipeline(self):
        url = "http://dlstreamer-pipeline-server:8080/pipelines/status"
        self.data = requests.get(url)
        return self.data.text

    def list_streams(self):
        # Placeholder for listing available streams
        pass

    def delete_stream(self, stream_id: str):
        url = f"http://dlsteamer-pipeline-server:8080/pipelines/{stream_id}"
        requests.delete(url)
        return {"message": f"Stream {stream_id} deleted successfully."}
    
    def view_stream(self, stream_id: str):
        url = f"http://dlstreamer-pipeline-server:8080/stream/{stream_id}"
        response = requests.get(url)
        self.stream_url = f"http://localhost:8889/{response}"
        return {f"{stream_id}": f"{self.stream_url}"}