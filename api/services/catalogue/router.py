from strawberry.fastapi import GraphQLRouter

from api.services.catalogue.schema import get_context, schema

router = GraphQLRouter(
    schema,
    path="/catalogue/graphql",
    graphql_ide=None,
    context_getter=get_context,
    tags=["Catalogue"],
)
