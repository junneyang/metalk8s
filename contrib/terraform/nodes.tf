resource "openstack_compute_instance_v2" "nodes" {
  count = var.nodes_count

  name        = "${local.prefix}-node-${count.index + 1}"
  image_name  = var.openstack_image_name
  flavor_name = var.openstack_flavours.nodes
  key_pair    = openstack_compute_keypair_v2.local_ssh_key.name

  scheduler_hints {
    group = openstack_compute_servergroup_v2.all_machines.id
  }

  security_groups = [openstack_networking_secgroup_v2.nodes.name]

  network {
    access_network = true
    name           = data.openstack_networking_network_v2.default_network.name
  }

  connection {
    host        = self.access_ip_v4
    type        = "ssh"
    user        = "centos"
    private_key = file(var.ssh_key_pair.private_key)
  }

  # Provision scripts for remote-execution
  provisioner "file" {
    source      = "${path.module}/scripts"
    destination = "/home/centos/scripts"
  }

  provisioner "remote-exec" {
    inline = ["chmod -R +x /home/centos/scripts"]
  }
}

locals {
  node_ips = [
    for node in openstack_compute_instance_v2.nodes : node.access_ip_v4
  ]
}
