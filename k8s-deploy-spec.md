# yt-download-api — K8s Deploy Spec

## Visão Geral

Deploy da aplicação no cluster k3s existente (node: `ubuntu-hl`), sem exposição pública.
Acesso restrito à rede interna do cluster via ClusterIP.

---

## Recursos Kubernetes

| Recurso | Nome | Namespace | Detalhe |
|---|---|---|---|
| Deployment | `yt-download-api` | `default` | 1 réplica, `imagePullPolicy: Always` |
| PVC | `yt-download-api-data` | `default` | 10Gi, `homelab-storage`, mount em `/app/data` |
| Secret | `yt-download-api-secrets` | `default` | `MANAGEMENT_SECRET`, `TOKEN_ENCRYPTION_KEY` |
| ConfigMap | `yt-download-api-config` | `default` | Configs não-sensíveis |
| Service | `yt-download-api` | `default` | ClusterIP, porta 8000 |

**Sem Ingress / Sem DNS** — acesso apenas interno ao cluster.

### Acesso interno
```
http://yt-download-api.default.svc.cluster.local:8000
```

### Acesso manual via port-forward
```bash
kubectl port-forward svc/yt-download-api 8000:8000 -n default
```

---

## Configuração

### Secret (valores gerados no deploy)
| Chave | Variável de Ambiente | Descrição |
|---|---|---|
| `management-secret` | `MANAGEMENT_SECRET` | Bearer token para rotas /admin |
| `token-encryption-key` | `TOKEN_ENCRYPTION_KEY` | Chave Fernet para criptografia de tokens |

### ConfigMap
| Chave | Valor Padrão | Descrição |
|---|---|---|
| `ALLOWED_ORIGINS` | `*` | CORS (sem frontend externo por ora) |
| `REQUEST_TIMEOUT_SECONDS` | `300` | Timeout download |
| `FASTER_WHISPER_MODEL` | `base` | Modelo Whisper |
| `FASTER_WHISPER_DEVICE` | `cpu` | Device de inferência |
| `FASTER_WHISPER_COMPUTE_TYPE` | `int8` | Tipo de precisão |
| `FASTER_WHISPER_CPU_THREADS` | `4` | Threads CPU |

### Resources do Pod
| | Request | Limit |
|---|---|---|
| CPU | 250m | 2000m |
| Memory | 1Gi | 3Gi |

---

## CI/CD

### Fluxo

```
Push para main
    │
    ├─► CI (ci.yml) — lint + syntax + docker build
    │
    └─► Deploy (deploy-image.yml) — build + push GHCR + rollout restart k8s
```

### Mudanças no deploy-image.yml

Substituir o step "Trigger Portainer webhook" por um step de rollout restart no k8s:

```yaml
- name: Rollout restart no Kubernetes
  uses: azure/k8s-set-context@v4
  with:
    method: kubeconfig
    kubeconfig: ${{ secrets.KUBECONFIG }}

- name: Restart deployment
  run: kubectl rollout restart deployment/yt-download-api -n default
```

### GitHub Secrets necessários

| Secret | Como obter |
|---|---|
| `KUBECONFIG` | `cat ~/.kube/config \| base64 -w0` no servidor k8s |

> O workflow já tem `GITHUB_TOKEN` para push no GHCR.

---

## Limitações Conhecidas

- **SQLite** — single-writer, máximo 1 réplica
- **Whisper** — primeiro request baixa o modelo (~100MB para `base`), pode demorar
- **Sem HTTPS** — tráfego interno apenas, sem TLS necessário
- **Sem scale-to-zero** — por ser rede privada, não há HTTPScaledObject (KEDA HTTP add-on requer Ingress)

---

## Ordem de Execução

1. Criar `Secret`
2. Criar `ConfigMap`
3. Criar `PVC`
4. Criar `Deployment`
5. Criar `Service`
6. Atualizar workflow `deploy-image.yml` no repositório
7. Configurar secret `KUBECONFIG` no GitHub
