# 🚀 Galileo Observability Integration

This document describes the comprehensive observability integration using **Galileo Python SDK** in your RAG application. The integration provides detailed monitoring, tracing, and analytics for all RAG operations.

## 🎯 **What is Galileo?**

**Galileo** is a comprehensive observability platform that provides:

- **📊 Real-time Monitoring**: Track system performance and health
- **🔍 Distributed Tracing**: Trace requests across microservices
- **📈 Metrics & Analytics**: Detailed performance metrics
- **🚨 Alerting**: Proactive issue detection and notification
- **📋 Dashboards**: Visual insights into system behavior

## 🏗️ **Observability Architecture**

Your RAG service now includes a complete observability stack:

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   RAG Service   │───▶│   Galileo 2.0   │───▶│   Dashboards    │
│                 │    │   Platform      │    │   & Analytics   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ OpenTelemetry   │    │   Prometheus    │    │  Structured     │
│   Tracing       │    │    Metrics      │    │   Logging       │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 🔧 **Configuration**

### **Environment Variables**

Add these to your `packages/rag/.env` file:

```env
# Galileo 2.0 Configuration
GALILEO_ENABLED=true
GALILEO_API_KEY=your-galileo-api-key-here
GALILEO_PROJECT_NAME=healthcare-rag
GALILEO_ENVIRONMENT=development

# OpenTelemetry Configuration
OTEL_ENABLED=true
OTEL_ENDPOINT=http://localhost:4317
OTEL_SERVICE_NAME=rag-service
OTEL_SERVICE_VERSION=0.1.0

# Prometheus Configuration
PROMETHEUS_ENABLED=true
PROMETHEUS_PORT=9090

# Logging Configuration
LOG_LEVEL=INFO
LOG_FORMAT=json
```

### **Getting Your Galileo API Key**

1. **Sign up for Galileo**: Visit [Galileo Platform](https://galileo.com)
2. **Create a project**: Set up your healthcare-rag project
3. **Get API key**: Copy your API key from the dashboard
4. **Configure environment**: Add the API key to your `.env` file

## 📊 **Metrics & Monitoring**

### **RAG-Specific Metrics**

Your RAG service now tracks these key metrics:

#### **Query Performance**
- `rag_queries_total`: Total number of RAG queries
- `rag_query_duration_seconds`: Query response time
- `rag_vector_search_duration_seconds`: Vector search performance
- `rag_ai_response_duration_seconds`: AI response generation time

#### **Document Operations**
- `rag_document_uploads_total`: Document upload counts
- `rag_embeddings_stored_total`: Embedding storage operations
- `rag_embedding_generation_duration_seconds`: Embedding generation time

#### **System Health**
- `rag_errors_total`: Error counts by type
- `rag_active_connections`: Active user connections

### **Accessing Metrics**

#### **Prometheus Endpoint**
```bash
# Get metrics in Prometheus format
curl http://localhost:8003/metrics
```

#### **Example Metrics Output**
```
# HELP rag_queries_total Total number of RAG queries
# TYPE rag_queries_total counter
rag_queries_total{query_type="ask",user_role="doctor",department="cardiology"} 42

# HELP rag_query_duration_seconds RAG query duration in seconds
# TYPE rag_query_duration_seconds histogram
rag_query_duration_seconds_bucket{query_type="ask",le="0.1"} 15
rag_query_duration_seconds_bucket{query_type="ask",le="0.5"} 35
rag_query_duration_seconds_bucket{query_type="ask",le="1.0"} 42
```

## 🔍 **Distributed Tracing**

### **Trace Structure**

Each RAG operation creates a detailed trace:

```
RAG Query (query_id: abc-123)
├── Vector Search (search_id: def-456)
│   ├── Database Query
│   ├── Embedding Generation
│   └── Similarity Calculation
├── AI Response Generation (response_id: ghi-789)
│   ├── Context Preparation
│   ├── OpenAI API Call
│   └── Response Processing
└── Galileo Event Logging
```

### **Trace Attributes**

Traces include rich metadata:

- **User Information**: Role, department, user ID
- **Query Details**: Query type, parameters, filters
- **Performance Data**: Duration, token counts, result counts
- **System Context**: Model versions, configuration

### **Viewing Traces**

1. **Galileo Dashboard**: View traces in the Galileo web interface
2. **Jaeger UI**: If using Jaeger for trace visualization
3. **OpenTelemetry Collector**: Forward traces to your preferred backend

## 📝 **Structured Logging**

### **Log Format**

All logs are now structured and include:

```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "level": "INFO",
  "logger": "rag_service.routers.chat",
  "message": "RAG query completed",
  "query_type": "ask",
  "user_role": "doctor",
  "department": "cardiology",
  "query_id": "abc-123",
  "duration": 1.234,
  "sources_count": 3,
  "context_used": true
}
```

### **Log Levels**

- **DEBUG**: Detailed debugging information
- **INFO**: General operational information
- **WARNING**: Potential issues or unusual behavior
- **ERROR**: Error conditions that need attention

### **Log Configuration**

```env
# JSON format for production
LOG_FORMAT=json

# Console format for development
LOG_FORMAT=console

# Log level
LOG_LEVEL=INFO
```

## 🎯 **Event Tracking**

### **Galileo Events**

The system automatically logs events to Galileo:

#### **Document Operations**
- `document_created`: New document creation
- `document_uploaded_with_embeddings`: Document upload with embedding generation
- `document_deleted`: Document deletion
- `embeddings_regenerated`: Embedding regeneration

#### **RAG Operations**
- `document_search`: Document search queries
- `ai_question_answered`: AI question responses
- `ai_response_error`: AI response generation errors
- `ai_response_feedback`: User feedback on responses

#### **System Events**
- `embedding_generation_started`: Embedding generation begins
- `vector_search_completed`: Vector search operations
- `rag_query_started`: RAG query initiation

### **Event Data Structure**

Each event includes:

```json
{
  "event_type": "ai_question_answered",
  "event_data": {
    "question": "What are the treatment guidelines?",
    "context_used": true,
    "sources_count": 3,
    "response_length": 245,
    "input_tokens": 12,
    "output_tokens": 89,
    "model": "gpt-4o-mini",
    "response_id": "ghi-789"
  },
  "user_id": "123",
  "session_id": "abc-123",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

## 🚀 **Performance Monitoring**

### **Key Performance Indicators (KPIs)**

#### **Response Time**
- **Target**: < 2 seconds for RAG queries
- **Monitoring**: `rag_query_duration_seconds` histogram
- **Alerting**: Set up alerts for queries > 5 seconds

#### **Accuracy**
- **Target**: High relevance in search results
- **Monitoring**: `rag_vector_search_duration_seconds` and result counts
- **Feedback**: User feedback tracking via `ai_response_feedback` events

#### **System Health**
- **Target**: 99.9% uptime
- **Monitoring**: Error rates via `rag_errors_total`
- **Alerting**: Error rate spikes

### **Dashboard Setup**

Create Galileo dashboards for:

1. **RAG Performance Dashboard**
   - Query response times
   - Success rates
   - User activity by role

2. **Document Operations Dashboard**
   - Upload rates
   - Embedding generation performance
   - Storage metrics

3. **System Health Dashboard**
   - Error rates
   - Active connections
   - Resource utilization

## 🔧 **Troubleshooting**

### **Common Issues**

#### **Galileo Connection Issues**
```bash
# Check Galileo API key
echo $GALILEO_API_KEY

# Test Galileo connection
curl -H "Authorization: Bearer $GALILEO_API_KEY" \
  https://api.galileo.com/health
```

#### **OpenTelemetry Issues**
```bash
# Check OTLP endpoint
curl http://localhost:4317/health

# Verify trace export
# Check logs for "OpenTelemetry tracer initialized successfully"
```

#### **Prometheus Issues**
```bash
# Check metrics endpoint
curl http://localhost:8003/metrics

# Verify Prometheus can scrape
curl http://localhost:9090/api/v1/targets
```

### **Debug Mode**

Enable debug logging for troubleshooting:

```env
DEBUG=true
LOG_LEVEL=DEBUG
```

### **Health Check Endpoints**

```bash
# Service health
curl http://localhost:8003/health

# Observability status
curl http://localhost:8003/observability

# Prometheus metrics
curl http://localhost:8003/metrics
```

## 📈 **Analytics & Insights**

### **Query Analytics**

Track query patterns and performance:

- **Most common queries**: Identify popular questions
- **Query performance**: Find slow queries
- **User behavior**: Understand usage patterns by role
- **Error analysis**: Identify common failure points

### **Document Analytics**

Monitor document operations:

- **Upload patterns**: Track document types and sizes
- **Embedding performance**: Monitor generation times
- **Storage efficiency**: Track embedding storage usage
- **Access patterns**: Understand document usage

### **AI Performance**

Monitor AI model performance:

- **Response quality**: Track user feedback
- **Token usage**: Monitor OpenAI API costs
- **Model performance**: Compare different models
- **Context effectiveness**: Measure context usage

## 🚀 **Production Deployment**

### **Production Configuration**

```env
# Production settings
GALILEO_ENVIRONMENT=production
LOG_LEVEL=WARNING
LOG_FORMAT=json
DEBUG=false

# Use production Galileo endpoint
GALILEO_API_KEY=your-production-galileo-api-key

# Use production OpenTelemetry collector
OTEL_ENDPOINT=https://your-otel-collector:4317
```

### **Monitoring Setup**

1. **Set up alerts** for critical metrics
2. **Configure dashboards** for key KPIs
3. **Set up log aggregation** for centralized logging
4. **Configure trace sampling** for production load

### **Performance Optimization**

1. **Trace sampling**: Sample traces in production
2. **Metric aggregation**: Aggregate metrics for efficiency
3. **Log rotation**: Implement log rotation policies
4. **Resource monitoring**: Monitor system resources

## 🎯 **Benefits**

### **For Developers**
- **Debugging**: Detailed traces for troubleshooting
- **Performance**: Identify bottlenecks and optimize
- **Monitoring**: Real-time system health visibility

### **For Operations**
- **Alerting**: Proactive issue detection
- **Capacity Planning**: Understand usage patterns
- **Incident Response**: Quick problem identification

### **For Business**
- **User Experience**: Monitor and improve response times
- **Cost Optimization**: Track API usage and costs
- **Quality Assurance**: Monitor AI response quality

## 📚 **Next Steps**

1. **Set up Galileo account** and get your API key
2. **Configure environment variables** for your deployment
3. **Create dashboards** for key metrics
4. **Set up alerts** for critical thresholds
5. **Monitor and optimize** based on insights

---

**Your RAG application now has enterprise-grade observability with Galileo** 🚀✨

**Need help?** Check the troubleshooting section or refer to the Galileo documentation for advanced features.
