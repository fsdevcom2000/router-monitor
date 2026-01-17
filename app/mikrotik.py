import re
import time
import ipaddress
from librouteros import connect
from librouteros.exceptions import TrapError



def is_private_ipv4(ip: str) -> bool:
    try:
        return ipaddress.ip_address(ip).is_private
    except ValueError:
        return True


def format_uptime(uptime_str: str) -> str:
    if not uptime_str:
        return "0min"

    matches = re.findall(r'(\d+)([wdhms])', uptime_str.lower())

    if not matches:
        return "0min"

    total_days = 0
    hours = 0
    minutes = 0

    for val, unit in matches:
        value = int(val)
        if unit == "w":
            total_days += value * 7
        elif unit == "d":
            total_days += value
        elif unit == "h":
            hours += value
        elif unit == "m":
            minutes += value
        # "s" ignore

    parts = []
    if total_days > 0:
        parts.append(f"{total_days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}min")

    if not parts:
        return "0min"

    return " ".join(parts)

class RouterAPI:
    def __init__(self, host, username, password, port=8728, name=None):
        self.host = host
        self.username = username
        self.password = password
        self.port = port
        self.api = None
        self.name = name
        self.reconnects = 0

    def connect(self):
        """Synchronous connection. Called internally to_thread."""
        try:
            self.api = connect(
                host=self.host,
                username=self.username,
                password=self.password,
                port=self.port,
            )
        except Exception:
            self.api = None

    def ensure_connected(self):
        if self.api is None:
            # Increase the reconnection counter, for statistics (if we have some unstable router)
            self.reconnects += 1
            self.connect()

    def close(self):
        """Carefully close the connection."""
        try:
            if self.api is not None:
                try:
                    self.api.close()
                except Exception:
                    pass
        finally:
            self.api = None

    def get_temperature_and_voltage(self):
        temperature = None
        voltage = None

        # New v7: /system/health
        try:
            for item in self.api.path("system", "health"):
                name = str(item.get("name", "")).lower()
                value = item.get("value")
                try:
                    value = float(value)
                except (TypeError, ValueError):
                    continue
                if "temp" in name or "temperature" in name:
                    temperature = value
                elif "volt" in name or "voltage" in name:
                    voltage = value
            if temperature is not None or voltage is not None:
                return temperature, voltage
        except Exception:
            pass

        # Old v6
        try:
            health = next(iter(self.api.path("system", "health")), None)
            if health:
                if "voltage" in health:
                    try:
                        voltage = float(health["voltage"])
                    except (TypeError, ValueError):
                        pass
                if "temperature" in health:
                    try:
                        temperature = float(health["temperature"])
                    except (TypeError, ValueError):
                        pass
            if temperature is not None or voltage is not None:
                return temperature, voltage
        except Exception:
            pass

        # Fallback — /system/resource
        try:
            resource = next(iter(self.api.path("system", "resource")), None)
            if resource:
                if "voltage" in resource:
                    try:
                        voltage = float(resource["voltage"])
                    except (TypeError, ValueError):
                        pass
                if "temperature" in resource:
                    try:
                        temperature = float(resource["temperature"])
                    except (TypeError, ValueError):
                        pass
        except Exception:
            pass

        return temperature, voltage

    def get_external_ipv4(self):
        self.ensure_connected()
        if not self.api:
            return None

        # 1. Trying to take an IP from /ip cloud (RouterOS 6/7)
        try:
            cloud = next(iter(self.api.path("ip", "cloud")), None)
            if cloud:
                ip = cloud.get("public-address")
                # MikroTik sometimes returns 0.0.0.0 while undecided
                if ip and ip != "0.0.0.0":
                    return ip
        except Exception:
            # if cloud is disabled/unavailable, just move on
            pass

        # 2. Fallback: trying to determine default route + interfaces
        try:
            # 2.1 Looking for default route in main
            default_route = None
            for r in self.api.path("ip", "route"):
                if r.get("dst-address") == "0.0.0.0/0" and r.get("routing-table") in (None, "main"):
                    # Take the first one that suits you
                    default_route = r
                    break

            if not default_route:
                return None

            iface = default_route.get("interface")
            gateway = default_route.get("gateway")

            # PPPoE/LTE: sometimes the interface is specified in gateway (for example, "pppoe-out1")
            if (not iface) and gateway and not gateway.replace(".", "").isdigit():
                iface = gateway

            # If still don’t understand the interface
            # try via DHCP/PPP/LTE without iface

            # 2.2 PPPoE WAN
            try:
                for ppp in self.api.path("interface", "pppoe-client"):
                    # if iface is known — filter
                    if iface and ppp.get("name") != iface:
                        continue
                    if ppp.get("running"):
                        ip = ppp.get("address")
                        if ip and ip != "0.0.0.0":
                            return ip
            except Exception:
                pass

            # 2.3 LTE WAN
            try:
                for lte in self.api.path("interface", "lte"):
                    if iface and lte.get("name") != iface:
                        continue
                    if lte.get("running"):
                        ip = lte.get("address")
                        if ip and ip != "0.0.0.0":
                            return ip
            except Exception:
                pass

            # 2.4 DHCP client
            try:
                for dhcp in self.api.path("ip", "dhcp-client"):
                    if iface and dhcp.get("interface") != iface:
                        continue
                    ip = dhcp.get("status-address")
                    if ip and ip != "0.0.0.0":
                        return ip
            except Exception:
                pass

            # 2.5 Static IP / VLAN WAN — classic /ip address
            try:
                if iface:
                    for addr in self.api.path("ip", "address"):
                        if addr.get("interface") == iface:
                            ip = addr.get("address", "").split("/")[0]
                            if ip and ip != "0.0.0.0":
                                return ip
            except Exception:
                pass

            # 2.6 Last try - if the gateway is public, return it
            try:
                if gateway and not is_private_ipv4(gateway):
                    return gateway
            except Exception:
                pass

            return None

        except Exception:
            return None

    def _resolve_iface_via_arp(self, gateway):
        if not gateway or gateway.replace(".", "").isdigit() is False:
            return None

        try:
            for arp in self.api.path("ip", "arp"):
                if arp.get("address") == gateway:
                    return arp.get("interface")
        except:
            pass

        return None

    def _get_interface_stats(self, iface):
        """
                Returns rx-byte, tx-byte for the interface.
                Searches in several places: interface, ethernet, switch.
                """

        def clean(v):
            if not v:
                return 0
            return int(str(v).replace(" ", ""))

        # 1. /interface
        for i in self.api.path("interface"):
            if i.get("name") == iface:
                rx = clean(i.get("rx-byte"))
                tx = clean(i.get("tx-byte"))
                if rx or tx:
                    return rx, tx

        # 2. /interface ethernet
        try:
            for i in self.api.path("interface", "ethernet"):
                if i.get("name") == iface:
                    rx = clean(i.get("rx-byte"))
                    tx = clean(i.get("tx-byte"))
                    if rx or tx:
                        return rx, tx
        except:
            pass

        # 3. /interface ethernet switch (some CRS)
        try:
            for i in self.api.path("interface", "ethernet", "switch"):
                if i.get("name") == iface:
                    rx = clean(i.get("rx-byte"))
                    tx = clean(i.get("tx-byte"))
                    if rx or tx:
                        return rx, tx
        except:
            pass

        return None, None

    def get_wan_rxtx(self):
        self.ensure_connected()
        if not self.api:
            return None

        try:
            # 1. Find default route
            default_route = None
            for r in self.api.path("ip", "route"):
                if r.get("dst-address") == "0.0.0.0/0" and r.get("routing-table") in (None, "main"):
                    default_route = r
                    break

            if not default_route:
                return None

            iface = default_route.get("interface")
            gateway = default_route.get("gateway")

            # PPPoE/LTE: the interface can be in gateway
            if not iface and gateway and not gateway.replace(".", "").isdigit():
                iface = gateway

            # If the interface is empty, try ARP
            if not iface:
                iface = self._resolve_iface_via_arp(gateway)

            # If the interface is strange (*D) - try immediate-gw
            if not iface or iface.startswith("*"):
                imm = default_route.get("immediate-gw")
                if imm and "%" in imm:
                    iface = imm.split("%")[1]

            if not iface:
                return None

            # 2. Get the first counters
            rx1, tx1 = self._get_interface_stats(iface)
            if rx1 is None:
                return None

            time.sleep(1)

            # 3. Get the second counters
            rx2, tx2 = self._get_interface_stats(iface)
            if rx2 is None:
                return None

            # 4. Calculate the speed
            rx_bps = (rx2 - rx1) * 8
            tx_bps = (tx2 - tx1) * 8

            return {
                "iface": iface,
                "rx_bps": rx_bps,
                "tx_bps": tx_bps,
                "rx_kbps": round(rx_bps / 1000, 2),
                "tx_kbps": round(tx_bps / 1000, 2),
                "rx_mbps": round(rx_bps / 1000 / 1000, 2),
                "tx_mbps": round(tx_bps / 1000 / 1000, 2),
            }

        except Exception:
            return None

    def get_wan_info(self):
        data = self.get_wan_rxtx()
        if not data:
            return None, None

        iface = data["iface"]
        # speed = f"rx: {data['rx_kbps']} kbps / tx: {data['tx_kbps']} kbps"
        speed = f"{data['rx_kbps']}/{data['tx_kbps']}"
        return iface, speed


    def get_logs(self, count=100):
        """
        Returns a list of dictionaries in a SINGLE format:
        {
            "time": str | None,
            "topics": list[str],
            "message": str,
            "raw": str,
            "source": "memory" | "disk"
        }
        """
        result = []

        try:
            self.ensure_connected()
            if not self.api:
                return []

            # --- MEMORY LOG ---
            try:
                logs = list(self.api(cmd="/log/print"))
                if isinstance(logs, list) and logs:
                    for item in logs[-count:]:
                        if not isinstance(item, dict):
                            continue

                        raw = item.get("message") or str(item)
                        topics = item.get("topics", "")
                        topics = [t for t in topics.split(",") if t]

                        result.append({
                            "time": item.get("time"),
                            "topics": topics,
                            "message": item.get("message", ""),
                            "raw": raw,
                            "source": "memory"
                        })

                    if result:
                        return result
            except:
                pass

            # --- DISK LOG ---
            try:
                files = list(self.api(cmd="/file/print"))
                log_files = [
                    f for f in files
                    if isinstance(f, dict)
                       and "log" in f.get("name", "").lower()
                       and "usb" not in f.get("name", "").lower()
                ]

                if not log_files:
                    return []

                name = log_files[-1].get("name")
                if not name:
                    return []

                content = self.api(
                    cmd="/file/get",
                    **{"numbers": name, "value-name": "contents"}
                )

                if isinstance(content, list) and content:
                    content = content[0]

                if isinstance(content, dict):
                    content = content.get("contents", b"")

                if isinstance(content, bytes):
                    content = content.decode(errors="ignore")

                if not isinstance(content, str):
                    return []

                lines = [l for l in content.split("\n") if l.strip()]
                for line in lines[-count:]:
                    # Попытка вытащить topics из строки
                    parts = line.split(" ")
                    topics = []
                    if len(parts) > 2 and "," in parts[2]:
                        topics = parts[2].split(",")

                    result.append({
                        "time": None,
                        "topics": topics,
                        "message": line,
                        "raw": line,
                        "source": "disk"
                    })

                return result

            except:
                return []

        except:
            return []


    def get_webfig_port(self):
        self.ensure_connected()
        if not self.api:
            return None

        try:
            services = list(self.api(cmd="/ip/service/print"))
            for s in services:
                if s.get("name") == "www":
                    return ("http", int(s.get("port", 80)))
                if s.get("name") == "www-ssl":
                    return ("https", int(s.get("port", 443)))
            return None
        except Exception:
            return None


    def get_status(self):
        """
        New version:
        - Any incompleteness of data → error
        - Any emptiness → error
        - Any garbage → error
        - Any problem with the API → error
        - Never returns a partially empty status
        """

        self.ensure_connected()
        if not self.api:
            return {"status": "No"}

        try:
            # --- 1. Get system/resource ---
            resource = next(iter(self.api.path("system", "resource")), None)

            # If RouterOS returns empty dict or None → this is error
            if not resource or not isinstance(resource, dict) or len(resource) < 3:
                self.close()
                return {"status": "No"}

            # --- 2. Critical fields ---
            board = resource.get("board-name")
            version = resource.get("version")
            uptime_raw = resource.get("uptime")

            # If key fields are missing → RouterOS API is in bad state
            if not board or not version or not uptime_raw:
                self.close()
                return {"status": "No"}

            # --- 3. CPU / Memory / HDD ---
            try:
                cpu_freq = int(resource.get("cpu-frequency"))
                cpu_load = int(resource.get("cpu-load"))
                free_mem = int(resource.get("free-memory"))
                total_mem = int(resource.get("total-memory"))
                free_hdd = int(resource.get("free-hdd-space"))
                total_hdd = int(resource.get("total-hdd-space"))
            except Exception:
                # Any parsing error → RouterOS API returned garbage
                self.close()
                return {"status": "No"}

            # --- 4. WAN / IP / Health ---
            temperature, voltage = self.get_temperature_and_voltage()
            ipv4 = self.get_external_ipv4()
            iface, speed = self.get_wan_info()
            proto, port = self.get_webfig_port() or ("http", 80)

            # --- 5. Forming a valid status ---
            return {
                "status": "Yes",
                "board": board,
                "version": version,
                "uptime": format_uptime(uptime_raw),
                "cpu_freq": cpu_freq,
                "cpu_load": cpu_load,
                "free_memory": round(free_mem / 1024 / 1024, 2),
                "total_memory": round(total_mem / 1024 / 1024, 2),
                "free_hdd": round(free_hdd / 1024 / 1024, 2),
                "total_hdd": round(total_hdd / 1024 / 1024, 2),
                "temperature": temperature,
                "voltage": voltage,
                "ipv4": ipv4,
                "iface": iface,
                "speed": speed,
                "reconnects": self.reconnects if self.reconnects else "-",
                "webfig_host": str(self.host),
                "webfig_proto": proto,
                "webfig_port": port,
            }

        except Exception:
            # Any error → RouterOS API is unstable → close the connection
            self.close()
            return {"status": "No"}
