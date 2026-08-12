# Ollama in the AI Lab

Ollama is the initial, simplest local model runtime. It is not the lab's model abstraction or its permanent model strategy.

## Recommended first approach: native on the T480 host

Run Ollama natively when first exploring CPU-only inference. It makes model management and host-level inspection simple. Docker applications can reach it through an explicitly configured endpoint; on Linux, a reliable option is to publish Ollama deliberately on the T480's private interface or use a host-gateway mapping for the application container. Do not assume `localhost` inside a container means the host.

## Alternative: Docker Compose profile

The root Compose file includes an optional `ollama` profile:

```bash
docker compose --profile ollama up -d
docker compose exec ollama ollama pull <chosen-model>
```

This keeps model files in the `ollama_models` named volume and makes the service available to other Compose services at `http://ollama:11434`. It is isolated and portable, but native host operation is the more straightforward initial learning path.

## Approved first embedding models

The first local retrieval evaluation uses these two models:

- `bge-m3` — BGE retrieval candidate available through the supported Ollama catalogue.
- `mxbai-embed-large` — a stronger retrieval-quality candidate, at the cost of more CPU time.

They share the single `ollama_models` named volume. A Docker volume belongs to the Ollama runtime, not to an individual model: it persists both downloaded models when the Ollama container is recreated. Do not create separate volumes for each model unless an explicit isolation or retention requirement emerges.

On the T480, the governed adapter operation `ollama_embeddings_install` starts the private Compose service and pulls exactly these models. It does not publish an Ollama port to the host or network.

## T480 expectations

The 16 GB RAM, CPU-only T480 is best for small, quantised models and embedding workloads. Start with roughly 2–4B parameter models in a suitable quantisation, then measure actual latency and memory use. Quantisation stores weights with fewer bits, reducing RAM and often improving CPU practicality at some potential quality cost. Treat embedding and reranking models as separate, task-specific choices.

Keep model artefacts separate from application code and never hard-code a model or Ollama URL into applications. Use a provider/model configuration layer so an application can move between Ollama, another local runtime, self-hosted cloud inference, and commercial APIs.
