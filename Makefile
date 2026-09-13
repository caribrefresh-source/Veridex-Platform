.DEFAULT_GOAL := help
ANSIBLE_DIR := ansible
ENV ?= staging

.PHONY: help
help: ## Show available targets
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}'

.PHONY: prepare-hosts
prepare-hosts: ## Baseline + firewall on all hosts
	cd $(ANSIBLE_DIR) && ansible-playbook -i inventory/$(ENV)/hosts.yml playbooks/prepare-hosts.yml

.PHONY: install-cluster
install-cluster: ## Install k3s servers then agents
	cd $(ANSIBLE_DIR) && ansible-playbook -i inventory/$(ENV)/hosts.yml playbooks/install-k3s-servers.yml
	cd $(ANSIBLE_DIR) && ansible-playbook -i inventory/$(ENV)/hosts.yml playbooks/install-k3s-agents.yml

# Must run between install-cluster and verify-cluster. The servers set
# flannel-backend=none, so every node -- agents included -- stays NotReady
# until this lands. Skipping it leaves a cluster where nothing schedules.
.PHONY: install-cilium
install-cilium: ## Install the Cilium CNI (cluster-wide, from the bootstrap server)
	cd $(ANSIBLE_DIR) && ansible-playbook -i inventory/$(ENV)/hosts.yml playbooks/install-cilium.yml

.PHONY: verify-cluster
verify-cluster: ## Check cluster health
	cd $(ANSIBLE_DIR) && ansible-playbook -i inventory/$(ENV)/hosts.yml playbooks/verify-cluster.yml

.PHONY: bootstrap-argocd
bootstrap-argocd: ## Install Argo CD and apply the root application
	cd $(ANSIBLE_DIR) && ansible-playbook -i inventory/$(ENV)/hosts.yml playbooks/bootstrap-argocd.yml

# The full bring-up in dependency order.
.PHONY: bring-up
bring-up: prepare-hosts install-cluster install-cilium verify-cluster bootstrap-argocd ## Run the whole bring-up in order

.PHONY: build
build: ## Render every environment kustomization
	kubectl kustomize kubernetes/environments/$(ENV) > /dev/null && echo "$(ENV) renders clean"

.PHONY: lint
lint: ## Lint ansible and kubernetes manifests
	ansible-lint $(ANSIBLE_DIR)
	kubectl kustomize kubernetes/environments/$(ENV) | kubeconform -strict -summary -

.PHONY: test
test: ## Run the test suite
	@echo "no tests yet"
