"""
Observability module for RAG service using Galileo 2.0, OpenTelemetry, and structured logging.
"""

import time
import uuid
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional

import structlog
from galileo_sdk import Galileo
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
    OTLPSpanExporter
)
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.openai import OpenAIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from prometheus_client import (
    Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
)
from fastapi import Request
from fastapi.responses import PlainTextResponse

from .config import settings

# Initialize structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer() if settings.log_format == "json" else structlog.dev.ConsoleRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)

# Prometheus metrics
RAG_QUERIES_TOTAL = Counter(
    "rag_queries_total",
    "Total number of RAG queries",
    ["query_type", "user_role", "department"]
)

RAG_QUERY_DURATION = Histogram(
    "rag_query_duration_seconds",
    "RAG query duration in seconds",
    ["query_type", "user_role", "department"]
)

RAG_EMBEDDING_GENERATION_DURATION = Histogram(
    "rag_embedding_generation_duration_seconds",
    "Embedding generation duration in seconds",
    ["model", "chunk_count"]
)

RAG_VECTOR_SEARCH_DURATION = Histogram(
    "rag_vector_search_duration_seconds",
    "Vector search duration in seconds",
    ["result_count", "similarity_threshold"]
)

RAG_AI_RESPONSE_DURATION = Histogram(
    "rag_ai_response_duration_seconds",
    "AI response generation duration in seconds",
    ["model", "token_count"]
)

RAG_DOCUMENT_UPLOADS = Counter(
    "rag_document_uploads_total",
    "Total number of document uploads",
    ["document_type", "department", "file_size"]
)

RAG_EMBEDDINGS_STORED = Counter(
    "rag_embeddings_stored_total",
    "Total number of embeddings stored",
    ["document_id", "chunk_count"]
)

RAG_ERRORS = Counter(
    "rag_errors_total",
    "Total number of RAG errors",
    ["error_type", "service"]
)

ACTIVE_CONNECTIONS = Gauge(
    "rag_active_connections",
    "Number of active connections"
)

# Galileo client
galileo_client: Optional[Galileo] = None

# OpenTelemetry tracer
tracer: Optional[trace.Tracer] = None


def initialize_observability():
    """Initialize all observability components."""
    global galileo_client, tracer
    
    logger.info("Initializing observability components")
    
    # Initialize Galileo 2.0
    if settings.galileo_enabled and settings.galileo_api_key:
        try:
            galileo_client = Galileo(
                api_key=settings.galileo_api_key,
                project_name=settings.galileo_project_name,
                environment=settings.galileo_environment
            )
            logger.info("Galileo 2.0 client initialized successfully")
        except Exception as e:
            logger.error("Failed to initialize Galileo client", error=str(e))
    
    # Initialize OpenTelemetry
    if settings.otel_enabled:
        try:
            # Create resource
            resource = Resource.create({
                "service.name": settings.otel_service_name,
                "service.version": settings.otel_service_version,
                "service.instance.id": str(uuid.uuid4()),
                "environment": settings.galileo_environment
            })
            
            # Create tracer provider
            provider = TracerProvider(resource=resource)
            
            # Add OTLP exporter
            otlp_exporter = OTLPSpanExporter(endpoint=settings.otel_endpoint)
            provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
            
            # Set global tracer provider
            trace.set_tracer_provider(provider)
            tracer = trace.get_tracer(__name__)
            
            logger.info("OpenTelemetry tracer initialized successfully")
        except Exception as e:
            logger.error("Failed to initialize OpenTelemetry", error=str(e))


def instrument_fastapi(app):
    """Instrument FastAPI application with OpenTelemetry."""
    if settings.otel_enabled:
        try:
            FastAPIInstrumentor.instrument_app(app)
            logger.info("FastAPI instrumented with OpenTelemetry")
        except Exception as e:
            logger.error("Failed to instrument FastAPI", error=str(e))


def instrument_sqlalchemy(engine):
    """Instrument SQLAlchemy engine with OpenTelemetry."""
    if settings.otel_enabled:
        try:
            SQLAlchemyInstrumentor().instrument(engine=engine)
            logger.info("SQLAlchemy instrumented with OpenTelemetry")
        except Exception as e:
            logger.error("Failed to instrument SQLAlchemy", error=str(e))


def instrument_openai():
    """Instrument OpenAI with OpenTelemetry."""
    if settings.otel_enabled:
        try:
            OpenAIInstrumentor().instrument()
            logger.info("OpenAI instrumented with OpenTelemetry")
        except Exception as e:
            logger.error("Failed to instrument OpenAI", error=str(e))


@asynccontextmanager
async def rag_query_context(
    query_type: str,
    user_role: str,
    department: str = None,
    query_id: str = None
):
    """Context manager for RAG query observability."""
    if query_id is None:
        query_id = str(uuid.uuid4())
    
    start_time = time.time()
    
    # Create span for tracing
    span = None
    if tracer:
        span = tracer.start_span(
            f"rag_query.{query_type}",
            attributes={
                "query_type": query_type,
                "user_role": user_role,
                "department": department,
                "query_id": query_id
            }
        )
    
    try:
        # Log query start
        logger.info(
            "RAG query started",
            query_type=query_type,
            user_role=user_role,
            department=department,
            query_id=query_id
        )
        
        # Increment counter
        RAG_QUERIES_TOTAL.labels(
            query_type=query_type,
            user_role=user_role,
            department=department or "unknown"
        ).inc()
        
        yield query_id
        
    except Exception as e:
        # Log error
        logger.error(
            "RAG query failed",
            query_type=query_type,
            user_role=user_role,
            department=department,
            query_id=query_id,
            error=str(e)
        )
        
        # Increment error counter
        RAG_ERRORS.labels(
            error_type=type(e).__name__,
            service="rag"
        ).inc()
        
        raise
    
    finally:
        # Calculate duration
        duration = time.time() - start_time
        
        # Record histogram
        RAG_QUERY_DURATION.labels(
            query_type=query_type,
            user_role=user_role,
            department=department or "unknown"
        ).observe(duration)
        
        # Log query completion
        logger.info(
            "RAG query completed",
            query_type=query_type,
            user_role=user_role,
            department=department,
            query_id=query_id,
            duration=duration
        )
        
        # End span
        if span:
            span.set_attribute("duration", duration)
            span.end()


@asynccontextmanager
async def embedding_generation_context(
    model: str,
    chunk_count: int,
    operation_id: str = None
):
    """Context manager for embedding generation observability."""
    if operation_id is None:
        operation_id = str(uuid.uuid4())
    
    start_time = time.time()
    
    # Create span for tracing
    span = None
    if tracer:
        span = tracer.start_span(
            "embedding_generation",
            attributes={
                "model": model,
                "chunk_count": chunk_count,
                "operation_id": operation_id
            }
        )
    
    try:
        logger.info(
            "Embedding generation started",
            model=model,
            chunk_count=chunk_count,
            operation_id=operation_id
        )
        
        yield operation_id
        
    except Exception as e:
        logger.error(
            "Embedding generation failed",
            model=model,
            chunk_count=chunk_count,
            operation_id=operation_id,
            error=str(e)
        )
        
        RAG_ERRORS.labels(
            error_type=type(e).__name__,
            service="embedding"
        ).inc()
        
        raise
    
    finally:
        duration = time.time() - start_time
        
        RAG_EMBEDDING_GENERATION_DURATION.labels(
            model=model,
            chunk_count=chunk_count
        ).observe(duration)
        
        logger.info(
            "Embedding generation completed",
            model=model,
            chunk_count=chunk_count,
            operation_id=operation_id,
            duration=duration
        )
        
        if span:
            span.set_attribute("duration", duration)
            span.end()


@asynccontextmanager
async def vector_search_context(
    result_count: int,
    similarity_threshold: float,
    search_id: str = None
):
    """Context manager for vector search observability."""
    if search_id is None:
        search_id = str(uuid.uuid4())
    
    start_time = time.time()
    
    # Create span for tracing
    span = None
    if tracer:
        span = tracer.start_span(
            "vector_search",
            attributes={
                "result_count": result_count,
                "similarity_threshold": similarity_threshold,
                "search_id": search_id
            }
        )
    
    try:
        logger.info(
            "Vector search started",
            result_count=result_count,
            similarity_threshold=similarity_threshold,
            search_id=search_id
        )
        
        yield search_id
        
    except Exception as e:
        logger.error(
            "Vector search failed",
            result_count=result_count,
            similarity_threshold=similarity_threshold,
            search_id=search_id,
            error=str(e)
        )
        
        RAG_ERRORS.labels(
            error_type=type(e).__name__,
            service="vector_search"
        ).inc()
        
        raise
    
    finally:
        duration = time.time() - start_time
        
        RAG_VECTOR_SEARCH_DURATION.labels(
            result_count=result_count,
            similarity_threshold=similarity_threshold
        ).observe(duration)
        
        logger.info(
            "Vector search completed",
            result_count=result_count,
            similarity_threshold=similarity_threshold,
            search_id=search_id,
            duration=duration
        )
        
        if span:
            span.set_attribute("duration", duration)
            span.end()


@asynccontextmanager
async def ai_response_context(
    model: str,
    token_count: int,
    response_id: str = None
):
    """Context manager for AI response generation observability."""
    if response_id is None:
        response_id = str(uuid.uuid4())
    
    start_time = time.time()
    
    # Create span for tracing
    span = None
    if tracer:
        span = tracer.start_span(
            "ai_response_generation",
            attributes={
                "model": model,
                "token_count": token_count,
                "response_id": response_id
            }
        )
    
    try:
        logger.info(
            "AI response generation started",
            model=model,
            token_count=token_count,
            response_id=response_id
        )
        
        yield response_id
        
    except Exception as e:
        logger.error(
            "AI response generation failed",
            model=model,
            token_count=token_count,
            response_id=response_id,
            error=str(e)
        )
        
        RAG_ERRORS.labels(
            error_type=type(e).__name__,
            service="ai_response"
        ).inc()
        
        raise
    
    finally:
        duration = time.time() - start_time
        
        RAG_AI_RESPONSE_DURATION.labels(
            model=model,
            token_count=token_count
        ).observe(duration)
        
        logger.info(
            "AI response generation completed",
            model=model,
            token_count=token_count,
            response_id=response_id,
            duration=duration
        )
        
        if span:
            span.set_attribute("duration", duration)
            span.end()


def log_document_upload(
    document_type: str,
    department: str,
    file_size: int,
    document_id: int
):
    """Log document upload metrics."""
    RAG_DOCUMENT_UPLOADS.labels(
        document_type=document_type,
        department=department,
        file_size=file_size
    ).inc()
    
    logger.info(
        "Document uploaded",
        document_type=document_type,
        department=department,
        file_size=file_size,
        document_id=document_id
    )


def log_embeddings_stored(
    document_id: int,
    chunk_count: int
):
    """Log embeddings storage metrics."""
    RAG_EMBEDDINGS_STORED.labels(
        document_id=document_id,
        chunk_count=chunk_count
    ).inc()
    
    logger.info(
        "Embeddings stored",
        document_id=document_id,
        chunk_count=chunk_count
    )


def log_galileo_event(
    event_type: str,
    event_data: Dict[str, Any],
    user_id: str = None,
    session_id: str = None
):
    """Log event to Galileo 2.0."""
    if galileo_client:
        try:
            galileo_client.log_event(
                event_type=event_type,
                event_data=event_data,
                user_id=user_id,
                session_id=session_id
            )
            logger.debug(
                "Event logged to Galileo",
                event_type=event_type,
                user_id=user_id,
                session_id=session_id
            )
        except Exception as e:
            logger.error(
                "Failed to log event to Galileo",
                event_type=event_type,
                error=str(e)
            )


async def prometheus_metrics_endpoint():
    """Prometheus metrics endpoint."""
    return PlainTextResponse(
        generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )


class ObservabilityMiddleware:
    """FastAPI middleware for observability."""
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            request = Request(scope, receive)
            
            # Track active connections
            ACTIVE_CONNECTIONS.inc()
            
            start_time = time.time()
            
            # Create span for request
            span = None
            if tracer:
                span = tracer.start_span(
                    "http_request",
                    attributes={
                        "http.method": request.method,
                        "http.url": str(request.url),
                        "http.route": request.url.path,
                        "user_agent": request.headers.get("user-agent", ""),
                        "client_ip": request.client.host if request.client else ""
                    }
                )
            
            try:
                await self.app(scope, receive, send)
            except Exception as e:
                if span:
                    span.record_exception(e)
                raise
            finally:
                duration = time.time() - start_time
                
                if span:
                    span.set_attribute("duration", duration)
                    span.end()
                
                ACTIVE_CONNECTIONS.dec()
                
                logger.info(
                    "HTTP request completed",
                    method=request.method,
                    path=request.url.path,
                    duration=duration,
                    status_code=getattr(scope, "status_code", 500)
                )
        else:
            await self.app(scope, receive, send)
