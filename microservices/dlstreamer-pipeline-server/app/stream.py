
import os
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
        self.ip = os.environ.get("ip")
        self.streaminfo = {}

    def add_stream(self, stream_path, model_path, target_device):
        hex_v = str(os.urandom(8).hex())
        self.payload = {
        "source":{
            "uri":f"{stream_path}",
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
                "peer-id":f"pallet-defect-detection-{hex_v}"
            }
        },
        "parameters":{
            "detection-properties":{
                "model":f"{model_path}",
                "device":f"{target_device}"
            }
        }
        }

        url = f"http://{self.ip}:8080/pipelines/user_defined_pipelines/pallet_defect_detection"
        response = requests.post(url, json=self.payload, headers={"Content-Type": "application/json"})
        response.raise_for_status()
        self.stream_id = response.text.replace('"', '').strip()
        self.streaminfo[self.stream_id] = target_device
        return response.text
        #return self.streaminfo


    def view_metadata(self, file_path):
        file_path = urllib.parse.quote(file_path)
        url = f"http://{self.ip}:8080/metadata/{file_path}"
        self.metadata = requests.get(url)
        return self.metadata.text
    
    def view_pipeline(self):
        url = f"http://{self.ip}:8080/pipelines/status"
        self.data = requests.get(url)
        return self.data.text
    

    def delete_stream(self, stream_id: str):
        url = f"http://{self.ip}:8080/pipelines/{stream_id}"
        requests.delete(url)
        return {"message": f"Stream {stream_id} deleted successfully."}
    
    def view_stream(self, stream_id: str):
        url = f"http://{self.ip}:8080/stream/{stream_id}"
        response = requests.get(url)
        escaped_response = response.text.replace('"', '')
        self.stream_url = f"http://{self.ip}:8889/{escaped_response}"
        target_device = self.streaminfo.get(stream_id)
        return {f"{stream_id}": {"target_device": f"{target_device}", "url": f"{self.stream_url}"}}
    
    
