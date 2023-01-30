class Parameters:
    host: str = None
    port: str = None
    index_fields: str = None  # concatenated string of fields for indexing
    data: str = None
    code: str = None
    state: str = None
    secured: bool = False
    top_k: int = 9


S3_DEMO_PATH = 'https://jina-now-demo.s3.eu-central-1.amazonaws.com/'

ds_set = [
    'nft-monkey',
    'deepfashion',
    'nih-chest-xrays',
    'stanford-cars',
    'bird-species',
    'best-artworks',
    'geolocation-geoguessr',
    'rock-lyrics',
    'pop-lyrics',
    'rap-lyrics',
    'indie-lyrics',
    'metal-lyrics',
    'tumblr-gifs',
    'tumblr-gifs-10k',
]

SURVEY_LINK = 'https://10sw1tcpld4.typeform.com/to/VTAyYRpR?utm_source=cli'

BUTTONS = {
    'twitter': """
                <a href="https://twitter.com/share?ref_src=twsrc%5Etfw" class="twitter-share-button"
                Tweet
                </a>
                <script async src="https://platform.twitter.com/widgets.js" charset="utf-8"></script>
            """,
    'linkedin': """
                <a href="https://www.linkedin.com/sharing/share-offsite/?url=https://now.jina.ai"
                class="linkedin-share-button"
                rel="noreferrer noopener" when using target="_blank">
                </a>
                <script src="https://platform.linkedin.com/in.js" type="text/javascript">lang: en_US</script>
                <script type="IN/Share" data-url="https://now.jina.ai"></script>
            """,
    'facebook': """
                <a href="https://www.facebook.com/sharer.php?u=https://now.jina.ai" class="facebook-share-button"
                rel="noreferrer noopener" when using target="_blank">
                </a>
                <div id="fb-root"></div>
                <script async defer crossorigin="anonymous"
                src="https://connect.facebook.net/en_GB/sdk.js#xfbml=1&version=v14.0" nonce="kquhy3fp"></script>
                <div class="fb-share-button" data-href="https://now.jina.ai" data-layout="button" data-size="small">
                <a target="_blank"
                 href="https://www.facebook.com/sharer/sharer.php?u=https%3A%2F%2Fnow.jina.ai%2F&amp;src=sdkpreparse"
                  class="fb-xfbml-parse-ignore">Share</a></div>
            """,
}

SSO_COOKIE = 'st'
AVATAR_COOKIE = 'AvatarUrl'
TOKEN_COOKIE = 'JinaNOW_Token'
