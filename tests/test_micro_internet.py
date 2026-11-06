"""
Unit Tests for OmniNet Micro Internet Engine:
Pillars 1 to 5 (DID, Identity Resolver, Multipath Transport, Gateway Federation, Cooperative Network).
"""

import os
import shutil
import tempfile
import unittest
from unittest.mock import patch

from netopt.micro_internet import (
    DeviceDID,
    IdentityResolver,
    MultipathIdentityTransport,
    GatewayFederation,
    CooperativeNetwork,
    MicroInternetOrchestrator,
    get_micro_internet_orchestrator
)
from netopt.llm_gateway import LLMGateway


class TestMicroInternet(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.id_file = os.path.join(self.temp_dir, "test_identity.json")
        self.peers_file = os.path.join(self.temp_dir, "test_peers.json")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_pillar_1_device_did(self):
        # 1. Generate identity
        dev = DeviceDID(storage_path=self.id_file)
        self.assertTrue(dev.did.startswith("did:omninet:"))
        self.assertEqual(len(dev.public_key), 64)

        # 2. Persistence check
        dev2 = DeviceDID(storage_path=self.id_file)
        self.assertEqual(dev.did, dev2.did)
        self.assertEqual(dev.public_key, dev2.public_key)

        # 3. Cryptographic signature & document
        sig = dev.sign_message("hola micro internet")
        self.assertEqual(len(sig), 64)
        self.assertTrue(dev.verify_message("hola micro internet", sig, dev.public_key))

        doc = dev.export_document()
        self.assertEqual(doc["id"], dev.did)
        self.assertIn("verificationMethod", doc)

    def test_pillar_2_identity_resolver(self):
        resolver = IdentityResolver(cache_file=self.peers_file)
        peer_did = "did:omninet:peer_laptop_001"

        # Register node
        resolver.register_or_update(
            did=peer_did,
            ip="192.168.1.150",
            port=7788,
            transports=["MPQUIC", "UDP"],
            device_name="Laptop Living"
        )

        resolved = resolver.resolve(peer_did)
        self.assertIsNotNone(resolved)
        self.assertEqual(resolved["current_ip"], "192.168.1.150")
        self.assertEqual(resolved["status"], "ONLINE")

        # Roaming simulation: device moves to another Wi-Fi or subnet
        resolver.register_or_update(
            did=peer_did,
            ip="10.0.0.45",
            port=7789,
            transports=["MPQUIC"],
            device_name="Laptop Living"
        )

        roamed = resolver.resolve(peer_did)
        self.assertEqual(roamed["current_ip"], "10.0.0.45")
        self.assertEqual(roamed["port"], 7789)

        nodes = resolver.list_known_nodes()
        self.assertGreaterEqual(len(nodes), 1)

    def test_pillar_3_multipath_transport(self):
        dev = DeviceDID(storage_path=self.id_file)
        resolver = IdentityResolver(cache_file=self.peers_file)
        transport = MultipathIdentityTransport(dev)

        paths = transport.inspect_available_paths()
        self.assertGreaterEqual(len(paths), 1)

        # Route to registered node
        target_did = "did:omninet:target_node"
        resolver.register_or_update(target_did, "192.168.1.200", 8899, ["UDP"])

        res = transport.route_payload(target_did, {"msg": "video_frame"}, resolver)
        self.assertTrue(res["success"])
        self.assertGreater(res["routed_bytes"], 0)
        self.assertEqual(res["envelope"]["target_did"], target_did)

        # Route to unknown node
        res_fail = transport.route_payload("did:omninet:inexistente", {}, resolver)
        self.assertFalse(res_fail["success"])

    def test_pillar_4_gateway_federation(self):
        gw_fed = GatewayFederation(primary_gateway="192.168.1.1")
        initial = gw_fed.elect_active_gateway()
        self.assertEqual(initial["active_gateway"], "192.168.1.1")
        self.assertEqual(initial["mode"], "PRIMARY_ISP_ONLY")

        # Register backup cooperative gateway
        gw_fed.register_federated_gateway(
            domain_name="Oficina_Reserva",
            gateway_did="did:omninet:gw_backup_office",
            gateway_ip="192.168.1.254",
            priority=1
        )

        elected = gw_fed.elect_active_gateway()
        self.assertEqual(elected["active_gateway"], "192.168.1.254")
        self.assertEqual(elected["mode"], "FEDERATED_COOPERATIVE")
        self.assertTrue(elected["redundancy_available"])

    def test_pillar_5_cooperative_network_media_exchange(self):
        dev = DeviceDID(storage_path=self.id_file)
        resolver = IdentityResolver(cache_file=self.peers_file)
        transport = MultipathIdentityTransport(dev)
        coop = CooperativeNetwork(dev, resolver, transport)

        # Publish media
        pub = coop.publish_shared_media(
            resource_id="rec-001",
            title="Video Presentación 4K",
            file_path="C:\\Videos\\presentacion.mp4",
            size_bytes=104857600,  # 100 MB
            media_type="video/mp4"
        )
        self.assertEqual(pub["size_mb"], 100.0)

        catalog = coop.list_available_media()
        self.assertEqual(len(catalog), 1)

        # Direct LAN transfer
        peer_did = "did:omninet:peer_pc"
        resolver.register_or_update(peer_did, "192.168.1.180", 9000, ["TCP"])

        xfer = coop.request_direct_p2p_transfer(peer_did, "rec-001")
        self.assertTrue(xfer["success"])
        self.assertEqual(xfer["transfer"]["cloud_usage_bytes"], 0)
        self.assertEqual(xfer["transfer"]["status"], "COMPLETED")
        self.assertIn("LAN", xfer["message"])

    def test_micro_internet_orchestrator_and_conversational_gateway(self):
        orch = get_micro_internet_orchestrator()
        status = orch.get_mesh_status()

        self.assertTrue(status["micro_internet_enabled"])
        self.assertTrue(status["local_did"].startswith("did:omninet:"))
        self.assertTrue(status["zero_cloud_dependency"])
        self.assertGreaterEqual(status["active_transports_count"], 1)

        # Test Conversational Intent in LLMGateway
        gw = LLMGateway()
        gw.config["api_key"] = ""
        res_chat = gw.chat("¿qué es micro internet y cómo colaboran los dispositivos?")
        self.assertEqual(res_chat["executed_tool"], "micro_internet_mesh")
        self.assertIn("Micro Internet OmniNet", res_chat["reply"])
        self.assertIn("DID", res_chat["reply"])
        self.assertIn("gigabit", res_chat["reply"])


if __name__ == "__main__":
    unittest.main()
