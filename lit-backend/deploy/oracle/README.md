# Oracle VM backend staging

This is a **private staging deployment** of the existing FastAPI backend. It keeps the confirmed binary model as the primary result, binds port 8000 to the VM's loopback interface, and uses an SSH tunnel for access. It does not publish the frontend or promote a filing-based model.

## VM to create

- Oracle Cloud **Always Free eligible VM.Standard.A1.Flex**, Ubuntu 24.04 ARM64, 2 OCPUs and 12 GB RAM, in the tenancy's home region. A 50 GB boot volume is enough to start; check the account's free volume allocation before increasing it.
- Assign a public IP and allow inbound **SSH (TCP 22)** from your IP. No inbound rule for 8000, 80, or 443 is needed for staging.
- Install Docker Engine and the Compose plugin using [Docker's Ubuntu instructions](https://docs.docker.com/engine/install/ubuntu/). Docker's Ubuntu packages support ARM64. Verify `sudo docker compose version`.

## Stage the backend

The deployment needs this workspace's current code, including changes that are still uncommitted. I can transfer it after SSH access is available; if you transfer it yourself, push these changes to a branch before cloning on the VM. From `lit-backend/deploy/oracle/` on the VM:

```bash
./prepare.sh
# Edit .env.stage: keep ALLOWED_ORIGINS=http://localhost:3000 for local UI testing.
# Set HUGGINGFACE_API_KEY if you have one; an empty value uses the local model.
./stage.sh
```

`prepare.sh` copies the checked-in **3-document** dated fixture index into `state/` only when no index exists. That is enough for staging checks and too small for public outcome use. The image includes the existing `outcome_classifier_binary.joblib`; it does not retrain or change its reported N=187 metrics. The container runs as an unprivileged user, stores the local embedding cache in a Docker volume, and mounts the precedent index read-only. `PRECEDENT_INDEX_PATH` prevents the API from changing that frozen index.

To use the local frontend through the tunnel, run this on your computer:

```bash
ssh -N -L 8000:127.0.0.1:8000 ubuntu@VM_PUBLIC_IP
```

Then run the frontend locally at `http://localhost:3000`; its development API default is `http://localhost:8000/api/v1`. The VM service is reachable only through the tunnel. To inspect service status on the VM: `sudo docker compose ps` and `sudo docker compose logs --tail=100 backend`.

## Replace the fixture before public use

Use the [pre-decision data guide](../../scripts/outcome_dataset/PREDECISION.md) to build a real dated precedent index. Copy it to `state/precedent_index.json` and recreate the container. Check `/api/v1/health/ready`, index stats, dated search, and a full browser analysis again. The public API domain and TLS reverse proxy should be configured only after the larger index is working and the staging tests pass.

The current frontend requires appellant type and filing date. A larger VM increases serving capacity; it does not change the model's validated accuracy. The separate filing dataset, holdout evaluation, and model promotion remain subsequent work.
