import pytest

from e911.cer import (CERClient, CERError, load_export_file, parse_switchport_export,
                      parse_unlocated_export, resolve_port_identifier)


def test_parse_switchport_export(samples):
    with open(samples["cer_switchports"], encoding="utf-8") as fh:
        status, ports = parse_switchport_export(fh.read())
    assert status == "Exporting info"
    assert len(ports) == 11
    gi14 = next(p for p in ports if p.if_name == "Gi1/0/14")
    assert gi14.switch_host == "sw-main-2f-idf3.example.org"
    assert gi14.switch_ip == "192.0.2.11"
    assert gi14.erl_name == "ERL_MAIN_3F_OR"
    assert gi14.port_identifier == "1/0/14"


def test_parse_unlocated_export(samples):
    with open(samples["cer_unlocated"], encoding="utf-8") as fh:
        status, phones = parse_unlocated_export(fh.read())
    assert status == "Exporting info"
    assert [p.mac for p in phones] == ["0011223344AA"]
    assert phones[0].effective_erl == "Default"


def test_subscriber_export_is_rejected(tmp_path):
    path = tmp_path / "sub.xml"
    path.write_text("<SwitchPort><status>Publisher is active. Cannot fetch information "
                    "from subscriber.</status></SwitchPort>")
    with pytest.raises(CERError):
        load_export_file(str(path), "switchport")


def test_resolve_port_identifier(samples):
    ports = load_export_file(samples["cer_switchports"], "switchport")
    assert resolve_port_identifier(ports, "sw-main-3f-idf1", "GigabitEthernet1/0/25") \
        .port_identifier == "1/0/25"
    assert resolve_port_identifier(ports, "192.0.2.11", "Gi1/0/12").erl_name == "ERL_MAIN_2F_ED"
    assert resolve_port_identifier(ports, "sw-unknown", "Gi1/0/1") is None


class FakeResponse:
    def __init__(self, status_code=200, text="", payload=None):
        self.status_code = status_code
        self.text = text
        self._payload = payload

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


class FakeSession:
    """Records calls and plays back canned CER responses."""

    def __init__(self, responses):
        self.responses = responses
        self.calls = []
        self.verify = True

    def _respond(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        for (m, suffix, needs_auth), response in self.responses.items():
            if m == method and url.endswith(suffix) and needs_auth == ("auth" in kwargs):
                return response
        raise AssertionError(f"unexpected {method} {url}")

    def get(self, url, **kwargs):
        return self._respond("GET", url, **kwargs)

    def put(self, url, **kwargs):
        return self._respond("PUT", url, **kwargs)


def test_client_session_flow_and_exports(samples):
    with open(samples["cer_switchports"], encoding="utf-8") as fh:
        switchports = fh.read()
    session = FakeSession({
        ("GET", "/discoverystatus", False): FakeResponse(401),
        ("GET", "/discoverystatus", True): FakeResponse(
            200, "<DiscoveryStatus><status>Discovery is complete.</status></DiscoveryStatus>"),
        ("GET", "/switchport/info", True): FakeResponse(200, switchports),
    })
    client = CERClient("cer-pub.example.org", "api", "secret", session=session)
    assert client.discovery_complete()
    assert len(client.export_switchports()) == 11
    # First request is the unauthenticated JSESSIONID request.
    assert session.calls[0][0] == "GET" and "auth" not in session.calls[0][2]
    assert all(call[1].startswith("https://cer-pub.example.org/cerappservices/export/")
               for call in session.calls)


def test_client_update_switchport_erl():
    session = FakeSession({
        ("PUT", "/cerappservices/service/switchport/", True): FakeResponse(
            200, payload={"status": "Success", "message": "Updated"}),
    })
    client = CERClient("cer-pub.example.org", "api", "secret", session=session)
    assert client.update_switchport_erl("192.0.2.11", ["1/0/14"], "ERL_MAIN_2F_ED")["status"] \
        == "Success"
    body = session.calls[0][2]["json"]
    assert body == {"IPaddress": "192.0.2.11", "Allports": "false",
                    "ERLName": "ERL_MAIN_2F_ED", "Ports": ["1/0/14"]}


def test_client_partial_failure_raises():
    session = FakeSession({
        ("PUT", "/cerappservices/service/switchport/", True): FakeResponse(
            200, payload={"status": "Partially failed", "message": "Failed for ports [1/0/99]"}),
    })
    client = CERClient("cer-pub.example.org", "api", "secret", session=session)
    with pytest.raises(CERError):
        client.update_switchport_erl("192.0.2.11", ["1/0/99"], "ERL_X")


def test_client_bad_credentials():
    session = FakeSession({
        ("GET", "/discoverystatus", False): FakeResponse(401),
        ("GET", "/discoverystatus", True): FakeResponse(401),
    })
    client = CERClient("cer-pub.example.org", "api", "wrong", session=session)
    with pytest.raises(CERError):
        client.discovery_status()
