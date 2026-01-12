from dataclasses import dataclass

@dataclass
class Router:
    name: str
    host: str
    username: str
    password: str      # decrypted
    port: int
    enabled: int
