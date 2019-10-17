{%- set node_name = pillar.orchestrate.node_name %}
{%- set version = pillar.metalk8s.nodes[node_name].version %}

{%- set kubeconfig = "/etc/kubernetes/admin.conf" %}
{%- set context = "kubernetes-admin@kubernetes" %}

{%- if node_name not in salt.saltutil.runner('manage.up') %}
Deploy salt-minion on a new node:
  salt.state:
    - ssh: true
    - roster: kubernetes
    - tgt: {{ node_name }}
    - saltenv: metalk8s-{{ version }}
    - sls:
      - metalk8s.roles.minion

Accept key:
  module.run:
    - saltutil.wheel:
      - key.accept
      - {{ node_name }}
    - require:
      - salt: Deploy salt-minion on a new node

Wait minion available:
  salt.runner:
    - name: metalk8s_saltutil.wait_minions
    - tgt: {{ node_name }}
    - require:
      - module: Accept key
    - require_in:
      - salt: Set grains
      - salt: Refresh the mine
      - salt: Cordon the node
{%- endif %}

Set grains:
  salt.state:
    - tgt: {{ node_name }}
    - saltenv: metalk8s-{{ version }}
    - sls:
      - metalk8s.node.grains

Refresh the mine:
  salt.function:
    - name: mine.update
    - tgt: '*'

Cordon the node:
  metalk8s_cordon.node_cordoned:
    - name: {{ node_name }}
    - kubeconfig: {{ kubeconfig }}
    - context: {{ context }}

{%- if not pillar.orchestrate.get('skip_draining', False) %}

Drain the node:
  metalk8s_drain.node_drained:
    - name: {{ node_name }}
    - ignore_daemonset: True
    - delete_local_data: True
    - force: True
    - kubeconfig: {{ kubeconfig }}
    - context: {{ context }}
    - require:
      - metalk8s_cordon: Cordon the node
    - require_in:
      - salt: Run the highstate

{%- endif %}

Refresh pillar before highstate:
  salt.function:
    - name: saltutil.refresh_pillar
    - tgt: {{ node_name }}

Run the highstate:
  salt.state:
    - tgt: {{ node_name }}
    - highstate: True
    - require:
      - salt: Set grains
      - salt: Refresh the mine
      - metalk8s_cordon: Cordon the node
      - salt: Refresh pillar before highstate

Wait for API server to be available:
  http.wait_for_successful_query:
  - name: https://{{ pillar.metalk8s.api_server.host }}:6443/healthz
  - match: 'ok'
  - status: 200
  - verify_ssl: false

Uncordon the node:
  metalk8s_cordon.node_uncordoned:
    - name: {{ node_name }}
    - kubeconfig: {{ kubeconfig }}
    - context: {{ context }}
    - require:
      - salt: Run the highstate
      - http: Wait for API server to be available

{%- set master_minions = salt['metalk8s.minions_by_role']('master') %}

# Work-around for https://github.com/scality/metalk8s/pull/1028
Kill kube-controller-manager on all master nodes:
  salt.function:
    - name: ps.pkill
    - tgt: "{{ master_minions | join(',') }}"
    - tgt_type: list
    - fail_minions: "{{ master_minions | join(',') }}"
    - kwarg:
        pattern: kube-controller-manager
    - require:
      - salt: Run the highstate

{%- if 'etcd' in pillar.get('metalk8s', {}).get('nodes', {}).get(node_name, {}).get('roles', []) %}

Register the node into etcd cluster:
  salt.runner:
    - name: state.orchestrate
    - pillar: {{ pillar | json  }}
    - mods:
      - metalk8s.orchestrate.register_etcd
    - require:
      - salt: Run the highstate

{%- endif %}
