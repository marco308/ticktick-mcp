# TickTick MCP Server - Deployment Guide

This guide covers deploying the TickTick MCP server as a remote service accessible to multiple AI providers.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Authentication Setup](#authentication-setup)
3. [Docker Deployment](#docker-deployment)
4. [Kubernetes Deployment](#kubernetes-deployment)
5. [Cloud Provider Deployment](#cloud-provider-deployment)
6. [Security Best Practices](#security-best-practices)
7. [Connecting AI Providers](#connecting-ai-providers)

## Prerequisites

- Docker and Docker Compose installed
- TickTick account with API credentials
- (Optional) Domain name for production deployment
- (Optional) SSL certificate for HTTPS

## Authentication Setup

Before deploying, you need to authenticate with TickTick to get access tokens:

1. **On your local machine**, clone and set up the repository:
   ```bash
   git clone https://github.com/marco308/ticktick-mcp.git
   cd ticktick-mcp
   ```

2. **Install dependencies**:
   ```bash
   # Install uv if you don't have it
   curl -LsSf https://astral.sh/uv/install.sh | sh
   
   # Create virtual environment and install
   uv venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   uv pip install -e .
   ```

3. **Run authentication**:
   ```bash
   uv run -m ticktick_mcp.cli auth
   ```
   
   This will:
   - Prompt for your Client ID and Client Secret
   - Open a browser for OAuth authorization
   - Save tokens to `.env` file

4. **Verify your `.env` file** contains:
   ```
   TICKTICK_CLIENT_ID=your_actual_client_id
   TICKTICK_CLIENT_SECRET=your_actual_client_secret
   TICKTICK_ACCESS_TOKEN=long_token_string
   TICKTICK_REFRESH_TOKEN=long_token_string
   ```

## Docker Deployment

### Quick Start with Docker Compose

1. **Copy your `.env` file** to the server:
   ```bash
   scp .env user@your-server:/path/to/ticktick-mcp/
   ```

2. **On the server**, start the container:
   ```bash
   docker-compose up -d
   ```

3. **Check logs**:
   ```bash
   docker-compose logs -f
   ```

4. **Access the server**: `http://your-server:8080/sse`

### Manual Docker Deployment

```bash
# Build the image
docker build -t ticktick-mcp .

# Run with environment variables
docker run -d \
  --name ticktick-mcp \
  --restart unless-stopped \
  -p 8080:8080 \
  -e TICKTICK_CLIENT_ID="${TICKTICK_CLIENT_ID}" \
  -e TICKTICK_CLIENT_SECRET="${TICKTICK_CLIENT_SECRET}" \
  -e TICKTICK_ACCESS_TOKEN="${TICKTICK_ACCESS_TOKEN}" \
  -e TICKTICK_REFRESH_TOKEN="${TICKTICK_REFRESH_TOKEN}" \
  ticktick-mcp

# Check logs
docker logs -f ticktick-mcp
```

### Using Docker Secrets (More Secure)

```bash
# Create secrets
echo "your_access_token" | docker secret create ticktick_access_token -
echo "your_refresh_token" | docker secret create ticktick_refresh_token -

# Run with secrets (Docker Swarm)
docker service create \
  --name ticktick-mcp \
  --publish 8080:8080 \
  --secret ticktick_access_token \
  --secret ticktick_refresh_token \
  -e TICKTICK_CLIENT_ID="${TICKTICK_CLIENT_ID}" \
  -e TICKTICK_CLIENT_SECRET="${TICKTICK_CLIENT_SECRET}" \
  ticktick-mcp
```

## Kubernetes Deployment

### 1. Create a Secret

```bash
kubectl create secret generic ticktick-credentials \
  --from-literal=client-id="${TICKTICK_CLIENT_ID}" \
  --from-literal=client-secret="${TICKTICK_CLIENT_SECRET}" \
  --from-literal=access-token="${TICKTICK_ACCESS_TOKEN}" \
  --from-literal=refresh-token="${TICKTICK_REFRESH_TOKEN}"
```

### 2. Create Deployment

Create `k8s/deployment.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ticktick-mcp
  labels:
    app: ticktick-mcp
spec:
  replicas: 1
  selector:
    matchLabels:
      app: ticktick-mcp
  template:
    metadata:
      labels:
        app: ticktick-mcp
    spec:
      containers:
      - name: ticktick-mcp
        image: ticktick-mcp:latest
        ports:
        - containerPort: 8080
          name: sse
        env:
        - name: TICKTICK_CLIENT_ID
          valueFrom:
            secretKeyRef:
              name: ticktick-credentials
              key: client-id
        - name: TICKTICK_CLIENT_SECRET
          valueFrom:
            secretKeyRef:
              name: ticktick-credentials
              key: client-secret
        - name: TICKTICK_ACCESS_TOKEN
          valueFrom:
            secretKeyRef:
              name: ticktick-credentials
              key: access-token
        - name: TICKTICK_REFRESH_TOKEN
          valueFrom:
            secretKeyRef:
              name: ticktick-credentials
              key: refresh-token
        livenessProbe:
          httpGet:
            path: /sse
            port: 8080
          initialDelaySeconds: 10
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /sse
            port: 8080
          initialDelaySeconds: 5
          periodSeconds: 10
---
apiVersion: v1
kind: Service
metadata:
  name: ticktick-mcp
spec:
  selector:
    app: ticktick-mcp
  ports:
  - protocol: TCP
    port: 8080
    targetPort: 8080
  type: LoadBalancer
```

### 3. Apply Configuration

```bash
kubectl apply -f k8s/deployment.yaml
```

### 4. Get Service URL

```bash
kubectl get service ticktick-mcp
```

## Cloud Provider Deployment

### AWS (ECS/Fargate)

1. **Build and push image to ECR**:
   ```bash
   aws ecr create-repository --repository-name ticktick-mcp
   docker tag ticktick-mcp:latest ${AWS_ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/ticktick-mcp:latest
   docker push ${AWS_ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/ticktick-mcp:latest
   ```

2. **Create task definition** with environment variables from Secrets Manager

3. **Deploy to ECS/Fargate** with Application Load Balancer

### Google Cloud (Cloud Run)

```bash
# Build and push to GCR
gcloud builds submit --tag gcr.io/${PROJECT_ID}/ticktick-mcp

# Deploy to Cloud Run
gcloud run deploy ticktick-mcp \
  --image gcr.io/${PROJECT_ID}/ticktick-mcp \
  --platform managed \
  --port 8080 \
  --set-env-vars TICKTICK_CLIENT_ID="${TICKTICK_CLIENT_ID}" \
  --set-env-vars TICKTICK_CLIENT_SECRET="${TICKTICK_CLIENT_SECRET}" \
  --set-secrets TICKTICK_ACCESS_TOKEN=ticktick-access-token:latest \
  --set-secrets TICKTICK_REFRESH_TOKEN=ticktick-refresh-token:latest
```

### Azure (Container Instances)

```bash
# Push to ACR
az acr build --registry ${ACR_NAME} --image ticktick-mcp:latest .

# Deploy to ACI
az container create \
  --resource-group ${RESOURCE_GROUP} \
  --name ticktick-mcp \
  --image ${ACR_NAME}.azurecr.io/ticktick-mcp:latest \
  --dns-name-label ticktick-mcp \
  --ports 8080 \
  --environment-variables \
    TICKTICK_CLIENT_ID="${TICKTICK_CLIENT_ID}" \
    TICKTICK_CLIENT_SECRET="${TICKTICK_CLIENT_SECRET}" \
  --secure-environment-variables \
    TICKTICK_ACCESS_TOKEN="${TICKTICK_ACCESS_TOKEN}" \
    TICKTICK_REFRESH_TOKEN="${TICKTICK_REFRESH_TOKEN}"
```

## Security Best Practices

### 1. Use HTTPS with Reverse Proxy

Deploy nginx or Caddy as a reverse proxy:

**Nginx Configuration** (`/etc/nginx/sites-available/ticktick-mcp`):
```nginx
server {
    listen 443 ssl http2;
    server_name mcp.yourdomain.com;
    
    ssl_certificate /etc/letsencrypt/live/mcp.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/mcp.yourdomain.com/privkey.pem;
    
    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    
    location /sse {
        proxy_pass http://localhost:8080/sse;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
        proxy_read_timeout 86400;
        proxy_buffering off;
    }
}

# Redirect HTTP to HTTPS
server {
    listen 80;
    server_name mcp.yourdomain.com;
    return 301 https://$server_name$request_uri;
}
```

**Caddy Configuration** (`Caddyfile`):
```caddy
mcp.yourdomain.com {
    reverse_proxy /sse localhost:8080 {
        flush_interval -1
        header_up Host {host}
        header_up X-Real-IP {remote}
        header_up X-Forwarded-For {remote}
        header_up X-Forwarded-Proto {scheme}
    }
}
```

### 2. Firewall Configuration

```bash
# Allow only specific IPs
sudo ufw allow from YOUR_IP_ADDRESS to any port 8080
sudo ufw enable

# Or use iptables
iptables -A INPUT -p tcp -s YOUR_IP_ADDRESS --dport 8080 -j ACCEPT
iptables -A INPUT -p tcp --dport 8080 -j DROP
```

### 3. Environment Variable Security

- Never commit `.env` files
- Use secrets management (AWS Secrets Manager, GCP Secret Manager, etc.)
- Rotate tokens regularly
- Use least-privilege IAM roles

### 4. Network Security

- Deploy in private subnet with NAT gateway
- Use VPN or VPC peering for access
- Enable logging and monitoring
- Set up intrusion detection

### 5. Container Security

```dockerfile
# Run as non-root user
RUN useradd -m -u 1000 appuser
USER appuser

# Read-only filesystem
docker run --read-only --tmpfs /tmp ticktick-mcp
```

## Connecting AI Providers

### Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS):

```json
{
  "mcpServers": {
    "ticktick-remote": {
      "url": "https://mcp.yourdomain.com/sse"
    }
  }
}
```

### Other MCP-Compatible Clients

Configure with:
- **Transport**: SSE (Server-Sent Events)
- **URL**: `https://mcp.yourdomain.com/sse`
- **Authentication**: Bearer token (if implemented)

### API Gateway Integration

For advanced setups, integrate with API Gateway for:
- Rate limiting
- API key management
- Usage analytics
- DDoS protection

Example AWS API Gateway + Lambda setup available in the `examples/` directory.

## Monitoring and Maintenance

### Health Checks

```bash
# Check if server is responding
curl http://your-server:8080/sse

# Check Docker container health
docker inspect --format='{{.State.Health.Status}}' ticktick-mcp
```

### Logs

```bash
# Docker logs
docker logs -f ticktick-mcp

# Save logs to file
docker logs ticktick-mcp > ticktick-mcp.log 2>&1

# Kubernetes logs
kubectl logs -f deployment/ticktick-mcp
```

### Token Refresh

The server automatically refreshes tokens. Monitor logs for refresh events:
```
INFO - Access token refreshed successfully.
```

If tokens expire, re-run authentication locally and update environment variables.

## Troubleshooting

### Server Won't Start

1. Check environment variables are set:
   ```bash
   docker exec ticktick-mcp env | grep TICKTICK
   ```

2. Check logs for errors:
   ```bash
   docker logs ticktick-mcp
   ```

### Connection Refused

1. Check if port is accessible:
   ```bash
   telnet your-server 8080
   ```

2. Check firewall rules
3. Verify Docker port mapping:
   ```bash
   docker ps | grep ticktick-mcp
   ```

### Authentication Errors

1. Verify tokens haven't expired
2. Check Client ID and Secret are correct
3. Re-authenticate and update tokens

## Support

For issues and questions:
- GitHub Issues: https://github.com/marco308/ticktick-mcp/issues
- Documentation: https://github.com/marco308/ticktick-mcp/blob/main/README.md
