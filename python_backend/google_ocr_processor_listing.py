import warnings
from typing import List

from dataclasses import dataclass
from google.api_core.client_options import ClientOptions
from google.cloud import documentai_v1

warnings.filterwarnings("ignore", message="Your application has authenticated using end user credentials")

REGIONS = [
    "us",
    "eu",
    "asia-south1",
    "asia-southeast1",
    "australia-southeast1",
    "europe-west2",
    "northamerica-northeast1",
]

@dataclass
class Processor():
    project_id: str
    region: str
    processor_id: str
    processor_type: str
    processor_version: str

def list_processors(project_id: str) -> List[Processor]:
    results: List[Processor] = []
    for region in REGIONS:
        opts = ClientOptions(api_endpoint=f"{region}-documentai.googleapis.com")
        client = documentai_v1.DocumentProcessorServiceClient(client_options=opts)
        parent = client.common_location_path(project_id, region)
        try:
            for proc in client.list_processors(parent=parent):
                processor_id = proc.name.split("/")[-1]

                version_path = proc.default_processor_version or ""
                if version_path:
                    parts = client.parse_processor_version_path(version_path)
                    version = parts.get("processor_version", version_path)
                else:
                    version = ""
                    
                results.append(Processor(
                    project_id=project_id,
                    region=region,
                    processor_id=processor_id,
                    processor_type=proc.type_,
                    processor_version=version,
                ))
        except Exception as e:
            print(f"  Skipping {region}: {e}")
    return results

if __name__ == "__main__":
    project_id = "replace-with-your-project-id"

    for processor in list_processors(project_id):
        print(processor)