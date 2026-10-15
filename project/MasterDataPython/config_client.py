# Talks to vidya_configBE.service, the same config service the Go MasterData
# app (and udp_exchange_app's ConfigReader) use -- same host/port/token
# bootstrap, same Bearer-token auth, same POST /DataLoading route added to
# ConfigService/backend/src/routes/services.routes.js to return only the
# common (serviceType -1) config row, no per-service merge.
import configparser
import json
import urllib.request
from dataclasses import dataclass, field


@dataclass
class KafkaSetting:
    broker_ip: str = ""


@dataclass
class PostgresData:
    # NOTE: the source data's field naming is swapped from what you'd
    # expect -- "host" actually holds the port number, "hostname" holds the
    # actual host/address. Kept faithful to the real keys here; pg_loader.py
    # is what maps these into a real connection.
    ssl: str = "false"
    host: int = 0  # actually the PORT
    hostname: str = ""  # actually the HOST/address
    user: str = ""
    database: str = ""
    password: str = ""


@dataclass
class KafkaTopic:
    scrip_master_topic_name: str = ""
    master_topic_name: str = ""


@dataclass
class CommonConfig:
    service_id: int = 0
    service_name: str = ""
    kafka_setting: KafkaSetting = field(default_factory=KafkaSetting)
    postgres_data: PostgresData = field(default_factory=PostgresData)
    kafka_topic: KafkaTopic = field(default_factory=KafkaTopic)
    # Directory (e.g. "./"), not a filename -- combine with the actual .so
    # filename ("libcomm_channel.so") to get the real path, resolved
    # relative to wherever this process runs from.
    lib_comm_channel: str = ""

    @staticmethod
    def from_json(data: dict) -> "CommonConfig":
        pg = data.get(
            "postgressData", {}
        )  # note: double "s", matches the actual DB key
        kafka = data.get("kafkaSetting", {})
        topic = data.get("KafkaTopic", {})
        return CommonConfig(
            service_id=data.get("serviceId", 0),
            service_name=data.get("serviceName", ""),
            kafka_setting=KafkaSetting(broker_ip=kafka.get("brokerIp", "")),
            postgres_data=PostgresData(
                ssl=pg.get("ssl", "false"),
                host=pg.get("host", 0),
                hostname=pg.get("hostname", ""),
                user=pg.get("user", ""),
                database=pg.get("database", ""),
                password=pg.get("password", ""),
            ),
            kafka_topic=KafkaTopic(
                scrip_master_topic_name=topic.get("scripMasterTopicName", ""),
                master_topic_name=topic.get("masterTopicName", ""),
            ),
            lib_comm_channel=data.get("libCommChannel", ""),
        )


class ConfigClient:
    def __init__(self, ip: str, port: int, token: str, timeout: float = 5.0):
        self.ip = ip
        self.port = port
        self.token = token
        self.timeout = timeout

    @staticmethod
    def from_ini(path: str) -> "ConfigClient":
        parser = configparser.ConfigParser()
        if not parser.read(path):
            raise FileNotFoundError(f"{path}: could not be read")

        if "ConfigService" not in parser:
            raise ValueError(f"{path}: missing [ConfigService] section")
        section = parser["ConfigService"]

        ip = section.get("IP", "")
        token = section.get("Token", "")
        port_str = section.get("PORT", "")

        if not ip:
            raise ValueError(f"{path}: [ConfigService] is missing IP")
        if not token:
            raise ValueError(f"{path}: [ConfigService] is missing Token")
        if not port_str:
            raise ValueError(f"{path}: [ConfigService] is missing PORT")

        try:
            port = int(port_str)
        except ValueError as e:
            raise ValueError(f"{path}: [ConfigService] PORT: {e}")

        return ConfigClient(ip=ip, port=port, token=token)

    def fetch_common_data(self) -> CommonConfig:
        url = f"http://{self.ip}:{self.port}/DataLoading"
        req = urllib.request.Request(url, method="POST")
        req.add_header("Authorization", f"Bearer {self.token}")

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                status = resp.status
                body = resp.read()
        except urllib.error.HTTPError as e:
            raise RuntimeError(
                f"config-service returned HTTP {e.code} for /DataLoading"
            )
        except urllib.error.URLError as e:
            raise RuntimeError(f"request to config-service failed: {e}")

        if status != 200:
            raise RuntimeError(
                f"config-service returned HTTP {status} for /DataLoading"
            )

        try:
            data = json.loads(body)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"parsing /DataLoading response: {e}")

        return CommonConfig.from_json(data)
