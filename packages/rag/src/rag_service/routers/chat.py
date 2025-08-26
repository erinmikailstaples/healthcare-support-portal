import sys
from pathlib import Path

# Add the common package to Python path
common_path = Path(__file__).parent.parent.parent.parent.parent / "common" / "src"
sys.path.insert(0, str(common_path))


import openai
from common.auth import get_current_user
from common.db import get_db
from common.models import Document, User
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy_oso_cloud import authorized

from ..utils.embeddings import combine_chunks_for_context, similarity_search
from ..utils.text_processing import calculate_token_count

router = APIRouter()


# Request/Response Models
class ChatRequest(BaseModel):
    message: str
    context_patient_id: int | None = None
    context_department: str | None = None
    max_results: int | None = 5


class ChatResponse(BaseModel):
    response: str
    sources: list[dict]
    token_count: int
    context_used: bool


class SearchRequest(BaseModel):
    query: str
    document_types: list[str] | None = None
    department: str | None = None
    limit: int | None = 10


class SearchResponse(BaseModel):
    results: list[dict]
    total_results: int


@router.post("/search", response_model=SearchResponse)
async def search_documents(
    search_request: SearchRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Search documents using vector similarity
    """
    settings = request.app.state.settings

    # Get authorized documents query
    authorized_query = db.query(Document).options(
        authorized(current_user, "read", Document)
    )

    # Apply filters
    if search_request.document_types:
        authorized_query = authorized_query.filter(
            Document.document_type.in_(search_request.document_types)
        )

    if search_request.department:
        authorized_query = authorized_query.filter(
            Document.department == search_request.department
        )

    # Get authorized document IDs
    authorized_docs = authorized_query.all()
    authorized_doc_ids = [doc.id for doc in authorized_docs]

    if not authorized_doc_ids:
        return SearchResponse(results=[], total_results=0)

    # Perform similarity search
    results = await similarity_search(
        query_text=search_request.query,
        db=db,
        limit=search_request.limit or settings.max_results,
        similarity_threshold=settings.similarity_threshold,
        document_ids=authorized_doc_ids,
    )

    return SearchResponse(results=results, total_results=len(results))


@router.post("/ask", response_model=ChatResponse)
async def ask_question(
    chat_request: ChatRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Ask a question and get an AI-powered response with RAG
    """
    settings = request.app.state.settings

    # Get authorized documents for context
    authorized_query = db.query(Document).options(
        authorized(current_user, "read", Document)
    )

    # Apply context filters if provided
    if chat_request.context_patient_id:
        authorized_query = authorized_query.filter(
            Document.patient_id == chat_request.context_patient_id
        )

    if chat_request.context_department:
        authorized_query = authorized_query.filter(
            Document.department == chat_request.context_department
        )

    # Get authorized document IDs
    authorized_docs = authorized_query.all()
    authorized_doc_ids = [doc.id for doc in authorized_docs]

    sources = []
    context_used = False

    if authorized_doc_ids:
        # Perform similarity search
        search_results = await similarity_search(
            query_text=chat_request.message,
            db=db,
            limit=chat_request.max_results or settings.max_results,
            similarity_threshold=settings.similarity_threshold,
            document_ids=authorized_doc_ids,
        )

        sources = search_results
        context_used = len(search_results) > 0

    # Generate AI response
    try:
        ai_response = await generate_ai_response(
            question=chat_request.message,
            context_results=sources,
            user_role=current_user.role,
            settings=settings,
        )

        token_count = calculate_token_count(ai_response)

        return ChatResponse(
            response=ai_response,
            sources=sources,
            token_count=token_count,
            context_used=context_used,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating response: {str(e)}",
        )


async def generate_ai_response(
    question: str, context_results: list[dict], user_role: str, settings
) -> str:
    """
    Generate AI response using OpenAI with RAG context
    """
    # Prepare context from search results
    context = ""
    if context_results:
        context = combine_chunks_for_context(
            context_results, max_tokens=settings.max_context_length
        )

    # Create system prompt based on user role
    system_prompts = {
        "doctor": """You are an AI assistant helping a doctor in a healthcare setting. 
        Provide accurate, professional medical information based on the provided context. 
        Always remind users to verify information and consult current medical guidelines.""",
        "nurse": """You are an AI assistant helping a nurse in a healthcare setting. 
        Provide practical, relevant information for nursing care based on the provided context. 
        Focus on procedures, patient care, and safety protocols.""",
        "admin": """You are an AI assistant helping a healthcare administrator. 
        Provide information about policies, procedures, and administrative matters based on the provided context.""",
    }

    system_prompt = system_prompts.get(user_role, system_prompts["admin"])

    # Prepare messages
    messages = [
        {"role": "system", "content": system_prompt},
    ]

    if context:
        messages.append(
            {
                "role": "system",
                "content": f"Use the following context to answer the user's question:\n\n{context}",
            }
        )

    messages.append({"role": "user", "content": question})

    # Generate response using OpenAI
    try:
        client = openai.OpenAI()
        response = client.chat.completions.create(
            model=settings.chat_model,
            messages=messages,
            # max_tokens=1000,
            temperature=0.7,
        )

        ai_response = response.choices[0].message.content

        # Add disclaimer if no context was used
        if not context:
            ai_response += "\n\n*Note: This response was generated without specific document context. Please verify information with current medical guidelines.*"

        return ai_response

    except Exception as e:
        return f"I apologize, but I'm unable to generate a response at this time. Error: {str(e)}"


@router.get("/conversation-history")
async def get_conversation_history(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """
    Get conversation history for the current user
    Note: In a full implementation, you'd store conversation history in the database
    """
    # Placeholder - would implement conversation storage
    return {
        "message": "Conversation history feature not yet implemented",
        "user_id": current_user.id,
    }


@router.post("/feedback")
async def submit_feedback(
    response_id: str,
    rating: int,
    feedback: str | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Submit feedback on AI responses
    Note: In a full implementation, you'd store feedback in the database
    """
    # Placeholder - would implement feedback storage
    return {
        "message": "Thank you for your feedback",
        "response_id": response_id,
        "rating": rating,
    }
