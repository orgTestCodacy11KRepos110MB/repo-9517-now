# TODO bff_request_mapping_fn and bff_response_mapping_fn should be used to create all routes

import logging.config
import sys

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Mount

import deployment.bff.app.settings as api_settings
from deployment.bff.app.decorators import api_method, timed
from deployment.bff.app.v1.routers import (
    admin,
    cloud_temp_link,
    im_txt2im_txt,
    music2music,
    txt2txt_and_img,
    txt2video,
)

logging.config.dictConfig(api_settings.DEFAULT_LOGGING_CONFIG)
logger = logging.getLogger('bff.app')
logger.setLevel(api_settings.DEFAULT_LOGGING_LEVEL)

TITLE = 'Jina NOW'
DESCRIPTION = 'The Jina NOW service API'
AUTHOR = 'Jina AI'
EMAIL = 'hello@jina.ai'
__version__ = 'latest'


def get_app_instance():
    """Build FastAPI app."""
    app = FastAPI(
        title=TITLE,
        description=DESCRIPTION,
        contact={
            'author': AUTHOR,
            'email': EMAIL,
        },
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=['*'],
        allow_credentials=True,
        allow_methods=['*'],
        allow_headers=['*'],
    )

    @app.get('/ping')
    @api_method
    @timed
    def check_liveness() -> str:
        """
        Sanity check - this will let the caller know that the service is operational.
        """
        return 'pong!'

    @app.get('/')
    @api_method
    @timed
    def read_root() -> str:
        """
        Root path welcome message.
        """
        return (
            f'{TITLE} v{__version__} 🚀 {DESCRIPTION} ✨ '
            f'author: {AUTHOR} email: {EMAIL} 📄  '
            'Check out /docs or /redoc for the API documentation!'
        )

    @app.on_event('startup')
    def startup():
        logger.info(
            f'Jina NOW started! ' f'Listening to [::]:{api_settings.DEFAULT_PORT}'
        )

    @app.exception_handler(Exception)
    async def unicorn_exception_handler(request: Request, exc: Exception):
        import traceback

        error = traceback.format_exc()
        return JSONResponse(
            status_code=500,
            content={
                "message": f"Exception in BFF, but the root cause can still be in the flow: {error}"
            },
        )

    return app


def build_app():
    # cloud temporary link router
    cloud_temp_link_mount = '/api/v1/cloud-bucket-utils'
    cloud_temp_link_app = get_app_instance()
    cloud_temp_link_app.include_router(
        cloud_temp_link.router, tags=['Temporary-Link-Cloud']
    )

    # ImageTextRetrieval router
    im_txt2im_txt_mount = '/api/v1/image-or-text-to-image-or-text'
    im_txt2im_txt_app = get_app_instance()
    im_txt2im_txt_app.include_router(
        im_txt2im_txt.router, tags=['Image-Text Retrieval']
    )

    # Music2Music router
    music2music_mount = '/api/v1/music-to-music'
    music2music_app = get_app_instance()
    music2music_app.include_router(music2music.router, tags=['Music-To-Music'])

    # Text2Video router
    text2video_mount = '/api/v1/text-to-video'
    text2video_app = get_app_instance()
    text2video_app.include_router(txt2video.router, tags=['Text-To-Video'])

    # Text2TextAndImage router
    text2text_and_image_mount = '/api/v1/text-to-text-and-image'
    text2text_and_image_app = get_app_instance()
    text2text_and_image_app.include_router(
        txt2txt_and_img.router, tags=['Text-To-Text-And-Image']
    )

    # Admin router
    admin_mount = '/api/v1/admin'
    admin_app = get_app_instance()
    admin_app.include_router(admin.router, tags=['admin'])

    # Mount them - for other modalities just add an app instance
    app = Starlette(
        routes=[
            Mount(cloud_temp_link_mount, cloud_temp_link_app),
            Mount(im_txt2im_txt_mount, im_txt2im_txt_app),
            Mount(music2music_mount, music2music_app),
            Mount(text2video_mount, text2video_app),
            Mount(text2text_and_image_mount, text2text_and_image_app),
            Mount(admin_mount, admin_app),
        ]
    )
    return app


application = build_app()


def run_server(port=8080):
    """Run server."""
    app = build_app()
    uvicorn.run(
        app,
        host='0.0.0.0',
        port=port,
        loop='uvloop',
        http='httptools',
    )


if __name__ == '__main__':
    try:
        run_server(9090)
    except Exception as exc:
        logger.critical(str(exc))
        logger.exception(exc)
        sys.exit(1)
