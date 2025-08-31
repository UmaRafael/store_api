from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Body, Depends, HTTPException, Path, status, Query
from pydantic import UUID4
from store.core.exceptions import NotFoundException, ValidationException
from store.schemas.product import ProductIn, ProductOut, ProductUpdate, ProductUpdateOut
from store.usecases.product import ProductUsecase
from store.core.dependencies import get_usecase
from store.middlewares.logging import log_request
from store.core.pagination import PaginationParams, PaginatedResponse
from store.core.cache import cache_response, invalidate_cache

router = APIRouter(tags=["products"], prefix="/products")

@router.post(
    path="/",
    status_code=status.HTTP_201_CREATED,
    response_model=ProductOut,
    responses={
        201: {"description": "Produto criado com sucesso"},
        400: {"description": "Dados de entrada inválidos"},
        422: {"description": "Erro de validação dos dados"},
        500: {"description": "Erro interno do servidor"}
    },
    summary="Criar um novo produto",
    description="Cria um novo produto no sistema com os dados fornecidos"
)
@log_request
async def create_product(
    body: ProductIn = Body(..., example={
        "name": "Notebook Gamer",
        "price": 2500.00,
        "quantity": 10,
        "description": "Notebook para jogos de alta performance"
    }),
    usecase: ProductUsecase = Depends(get_usecase(ProductUsecase))
) -> ProductOut:
    """
    Cria um novo produto no sistema.
    
    - **name**: Nome do produto (obrigatório)
    - **price**: Preço do produto (obrigatório, deve ser positivo)
    - **quantity**: Quantidade em estoque (obrigatório, deve ser >= 0)
    - **description**: Descrição detalhada do produto (opcional)
    """
    try:
        result = await usecase.create(body=body)
        await invalidate_cache("products:list")
        return result
    except ValidationException as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=exc.message
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro interno ao criar produto"
        ) from exc


@router.get(
    path="/{id}",
    status_code=status.HTTP_200_OK,
    response_model=ProductOut,
    responses={
        200: {"description": "Produto encontrado"},
        404: {"description": "Produto não encontrado"},
        500: {"description": "Erro interno do servidor"}
    },
    summary="Buscar produto por ID",
    description="Retorna os detalhes de um produto específico pelo seu ID"
)
@log_request
@cache_response(key_prefix="product", expire=300)  # Cache de 5 minutos
async def get_product(
    id: UUID4 = Path(
        ...,
        alias="id",
        description="UUID do produto",
        example="550e8400-e29b-41d4-a716-446655440000"
    ),
    usecase: ProductUsecase = Depends(get_usecase(ProductUsecase))
) -> ProductOut:
    """
    Busca um produto pelo seu ID único.
    
    - **id**: UUID do produto (obrigatório)
    """
    try:
        return await usecase.get(id=id)
    except NotFoundException as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=exc.message
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro interno ao buscar produto"
        ) from exc


@router.get(
    path="/",
    status_code=status.HTTP_200_OK,
    response_model=PaginatedResponse[ProductOut],
    responses={
        200: {"description": "Lista de produtos retornada com sucesso"},
        500: {"description": "Erro interno do servidor"}
    },
    summary="Listar produtos",
    description="Retorna uma lista paginada de produtos com opções de filtro"
)
@log_request
@cache_response(key_prefix="products:list", expire=60)  # Cache de 1 minuto
async def list_products(
    category: Optional[str] = Query(
        None,
        description="Filtrar por categoria",
        example="eletronics"
    ),
    min_price: Optional[float] = Query(
        None,
        ge=0,
        description="Preço mínimo",
        example=100.0
    ),
    max_price: Optional[float] = Query(
        None,
        ge=0,
        description="Preço máximo",
        example=5000.0
    ),
    in_stock: Optional[bool] = Query(
        None,
        description="Apenas produtos em estoque"
    ),
    pagination: PaginationParams = Depends(),
    usecase: ProductUsecase = Depends(get_usecase(ProductUsecase))
) -> PaginatedResponse[ProductOut]:
    """
    Lista produtos com suporte a paginação e filtros.
    
    - **category**: Filtrar por categoria
    - **min_price**: Preço mínimo
    - **max_price**: Preço máximo  
    - **in_stock**: Apenas produtos com estoque > 0
    - **page**: Número da página (padrão: 1)
    - **size**: Tamanho da página (padrão: 20, máximo: 100)
    """
    try:
        filters = {
            "category": category,
            "min_price": min_price,
            "max_price": max_price,
            "in_stock": in_stock
        }
        return await usecase.query(
            filters=filters,
            page=pagination.page,
            size=pagination.size
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro interno ao listar produtos"
        ) from exc


@router.patch(
    path="/{id}",
    status_code=status.HTTP_200_OK,
    response_model=ProductUpdateOut,
    responses={
        200: {"description": "Produto atualizado com sucesso"},
        400: {"description": "Dados de entrada inválidos"},
        404: {"description": "Produto não encontrado"},
        422: {"description": "Erro de validação dos dados"},
        500: {"description": "Erro interno do servidor"}
    },
    summary="Atualizar produto parcialmente",
    description="Atualiza parcialmente os dados de um produto existente"
)
@log_request
async def update_product(
    id: UUID4 = Path(
        ...,
        alias="id",
        description="UUID do produto",
        example="550e8400-e29b-41d4-a716-446655440000"
    ),
    body: ProductUpdate = Body(
        ...,
        example={
            "price": 2300.00,
            "quantity": 15
        }
    ),
    usecase: ProductUsecase = Depends(get_usecase(ProductUsecase))
) -> ProductUpdateOut:
    """
    Atualiza parcialmente um produto existente.
    
    - **id**: UUID do produto (obrigatório)
    - **body**: Campos a serem atualizados (pelo menos um campo obrigatório)
    """
    try:
        if not body.dict(exclude_unset=True):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Pelo menos um campo deve ser fornecido para atualização"
            )
        
        result = await usecase.update(id=id, body=body)
        await invalidate_cache(f"product:{id}")
        await invalidate_cache("products:list")
        return result
        
    except NotFoundException as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=exc.message
        )
    except ValidationException as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=exc.message
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro interno ao atualizar produto"
        ) from exc


@router.delete(
    path="/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        204: {"description": "Produto deletado com sucesso"},
        404: {"description": "Produto não encontrado"},
        500: {"description": "Erro interno do servidor"}
    },
    summary="Deletar produto",
    description="Remove permanentemente um produto do sistema"
)
@log_request
async def delete_product(
    id: UUID4 = Path(
        ...,
        alias="id",
        description="UUID do produto",
        example="550e8400-e29b-41d4-a716-446655440000"
    ),
    usecase: ProductUsecase = Depends(get_usecase(ProductUsecase))
) -> None:
    """
    Deleta um produto permanentemente.
    
    - **id**: UUID do produto (obrigatório)
    """
    try:
        await usecase.delete(id=id)
        await invalidate_cache(f"product:{id}")
        await invalidate_cache("products:list")
    except NotFoundException as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=exc.message
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro interno ao deletar produto"
        ) from exc
