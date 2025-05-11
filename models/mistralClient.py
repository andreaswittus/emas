import requests

endpoint_id = "uixqqgyddx92"
api_key = "flp_hqZPNatZAZR9VABMmcqB7S3SYZ5YZNW2OHG0cQYy8NUO50"


class MistralClient:
    """
    Drop-in LLMClient replacement for FriendliAI using OpenAI-style completions.
    """

    def __init__(self, endpoint_id: str, api_key: str):
        self.api_url = "https://api.friendli.ai/dedicated/v1/completions"
        self.endpoint_id = endpoint_id
        self.api_key = api_key

    def generate(
        self, prompt: str, temperature: float = 0.7, max_tokens: int = 256
    ) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.endpoint_id,
            "prompt": prompt,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        response = requests.post(self.api_url, headers=headers, json=payload)

        if response.status_code != 200:
            raise RuntimeError(
                f"Friendli API error {response.status_code}:\n{response.text}"
            )

        result = response.json()
        return result["choices"][0]["text"].strip()
