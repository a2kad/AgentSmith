from dataclasses import dataclass


@dataclass
class GitHubClient:
    token: str

    def create_pull_request(self, *args, **kwargs) -> dict[str, str]:
        raise NotImplementedError("GitHub integration is not implemented yet")
