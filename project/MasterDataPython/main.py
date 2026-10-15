import json
import signal
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import comm_channel
import pg_loader
from config_client import ConfigClient


def build_handler(pg_config, producer, topic_name):
    class LoadBhavCopyHandler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass  # BaseHTTPRequestHandler's default per-request access log is noise here

        def do_POST(self):
            if self.path != "/load-bhavcopy":
                self.send_response(404)
                self.end_headers()
                return

            start = time.monotonic()

            def on_batch(batch):
                for row in batch:
                    producer.publish(topic_name, row.marshal_native())
                producer.flush()

            try:
                row_count = pg_loader.stream_main_bhavcopy(pg_config, 10000, on_batch)
            except Exception as e:
                print(f"load-bhavcopy: failed: {e}", flush=True)
                self.send_response(500)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(str(e).encode())
                return

            # Rounded to whole seconds -- raw sub-second precision is noise
            # for anything a human reads.
            elapsed_seconds = round(time.monotonic() - start)
            elapsed_str = f"{elapsed_seconds}s"
            print(
                f"load-bhavcopy: published {row_count} rows to topic {topic_name}, total time taken: {elapsed_str}",
                flush=True,
            )

            body = json.dumps(
                {
                    "rowsPublished": row_count,
                    "topic": topic_name,
                    "totalTimeTaken": elapsed_str,
                }
            ).encode()

            # Close this request's TCP connection once the response is sent,
            # instead of keeping it alive for reuse -- the service itself
            # stays running, only this per-request connection is not held
            # open.
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Connection", "close")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return LoadBhavCopyHandler


def main():
    client = ConfigClient.from_ini("config.ini")
    common_config = client.fetch_common_data()

    print(f"kafka broker: {common_config.kafka_setting.broker_ip}", flush=True)
    print(
        f"kafka topics: scripMaster={common_config.kafka_topic.scrip_master_topic_name} "
        f"master={common_config.kafka_topic.master_topic_name}",
        flush=True,
    )

    pg_config = common_config.postgres_data
    pg_loader.ping(pg_config)
    print(
        f"connected to postgres: {pg_config.user}@{pg_config.hostname}:{pg_config.host}/{pg_config.database}",
        flush=True,
    )

    lib_comm_channel_path = common_config.lib_comm_channel + "libcomm_channel.so"
    producer = comm_channel.Producer(
        lib_comm_channel_path, common_config.kafka_setting.broker_ip
    )

    handler_cls = build_handler(
        pg_config, producer, common_config.kafka_topic.master_topic_name
    )
    # Same port as the Go and C++ sibling apps (:8081) -- only one of the
    # three MasterData apps runs at a time, so a single port is one less
    # thing to remember instead of three.
    server = HTTPServer(("", 8081), handler_cls)

    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    print("server is up", flush=True)

    # Block here for the life of the process -- everything above (config,
    # Postgres connectivity, Kafka producer) stays set up the whole time.
    # Ctrl+C / SIGTERM triggers a graceful shutdown instead of just dying.
    stop_event = threading.Event()

    def handle_signal(signum, frame):
        stop_event.set()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    stop_event.wait()

    print("shutting down...", flush=True)
    server.shutdown()
    producer.close()


if __name__ == "__main__":
    main()
