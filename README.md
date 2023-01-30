<p align="center">

<img src="https://github.com/jina-ai/now/blob/main/docs/_static/logo-light.svg?raw=true" alt="Jina NOW logo: The data structure for unstructured data" width="300px">  


<br>
One command to host them all. Bring your search case into the cloud in minutes. <br>
Tell us what you think: <a href="https://10sw1tcpld4.typeform.com/to/VTAyYRpR?utm_source=cli">Survey</a>
</p>

<p align=center>
<a href="https://pypi.org/project/jina-now/"><img src="https://github.com/jina-ai/jina/blob/master/.github/badges/python-badge.svg?raw=true" alt="Python 3.7 3.8 3.9 3.10" title="Jina NOW supports Python 3.7 and above"></a>
<a href="https://pypi.org/project/jina-now/"><img src="https://img.shields.io/pypi/v/jina-now?color=%23099cec&amp;label=PyPI&amp;logo=pypi&amp;logoColor=white" alt="PyPI"></a>
</p>


<p align="center">
<img src="https://user-images.githubusercontent.com/11627845/164569398-5ef22a41-e2e1-438a-88a5-2ac43ad9426d.gif" alt="Jina NOW logo: The data structure for unstructured data" width="600px">

<!-- start elevator-pitch -->

NOW gives the world access to neural image search with just one command.
 
- ⛅ **Cloud**: We handle deployment and maintenance.
- 🐎 **Fast and easy**: Set up your search use case in minutes with minimal effort.
- 🌈 **Quality**: You provide the labels, NOW fine-tunes the model.
- ✨ **Nocode**: Non-technical people can deploy with ease.

Read how [Jina NOW is production ready](https://now.jina.ai/user-guides/production/).

### Install

```bash
pip install jina-now
```

If you need sudo to run Docker, use sudo to install and use Jina NOW as well.

```{important}
Jina NOW is only available on Linux and macOS.
```

#### Mac M1

For the M1 we recommend using a [Conda environment](https://docs.jina.ai/get-started/install/troubleshooting/#on-mac-m1).
In a new Conda environment:

1. Run `conda install grpcio tokenizers protobuf`
2. Run `pip install jina-now`.

### Quick start
```bash
jina now start
```
**1.** Choose your data source. 

You may either choose a demo dataset hosted by NOW, or use your own custom dataset, to build an application.
NOW can support your custom data in the form of a `DocumentArray`, as a path to a local folder, or S3 bucket.

```commandline
? How do you want to provide input? (format: https://docarray.jina.ai/)  (Use arrow keys)
 ❯ Demo dataset
   DocumentArray name (recommended)
   Local folder
   S3 bucket
   - Elasticsearch (will be available in upcoming versions)
```

You can choose a demo dataset to get started quickly. The demo datasets are hosted by NOW which can be easily
used to build a search application. There is a large variety of datasets, including images, text, and audio.

If you would like to use your own custom data, you can choose `DocumentArray name`. You will be asked to provide the
DocumentArray ID (or name) or URL of your dataset.

```commandline
? Please enter your DocumentArray name:
```

You can also choose the local folder option to upload your data, in which case
NOW asks for the path to the folder containing your data:

```commandline
? Please enter the path to the local folder:
```

Perhaps your data is stored in an S3 bucket, which is an option NOW also supports. In this case,
NOW asks for the URI to the S3 bucket, as well as the credentials and region thereof.

```commandline
? Please enter the S3 URI to the folder:
? Please enter the AWS access key ID:
? Please enter the AWS secret access key:
? Please enter the AWS region:
```

A final step in loading your data is to choose the fields of your data that you would like to use for search and filter
respectively. You can choose from the fields that are available in your data. For more information on this, see the
[guide to loading your data](https://now.jina.ai/user-guides/input_format/).


**2.** Follow the links. After NOW finishes processing, you'll see two links:

- The Swagger UI is useful for frontend integration.
- The "playground" lets you run example queries and experiment with your search use case.

```commandline
🚀 Deploy playground and BFF

BFF docs are accessible at:
http://localhost:30090/api/docs

Playground is accessible at:
http://localhost:30080/?host=gateway&search_field=image&data=best-artworks&port=8080
```

Example of the playground.

<img width="350" alt="Screenshot 2022-05-26 at 16 36 49" src="https://user-images.githubusercontent.com/11627845/170511607-3fb810f7-a5aa-47cd-9f70-e6034a96b9fd.png">

Example of the Swagger UI.

<img width="350" alt="Screenshot 2022-05-26 at 16 36 06" src="https://user-images.githubusercontent.com/11627845/170511580-230d1e41-5e14-4623-adb6-3d4b2d400dc9.png">

[More information on using Jina NOW CLI and API](https://now.jina.ai/user-guides/cli_api/)

## Supported modalities (more coming soon)

- 📝 Text
- 🏞 Image
- 🥁 Music
- 🎥 Video (for GIFs)
- 🧊 3D Mesh (coming soon)

[![](https://user-images.githubusercontent.com/11627845/164571632-0e6a6c39-0137-413b-8287-21fc34785665.png)](https://www.youtube.com/watch?v=fdIaLP0ctpo)
</p>
  
## Example datasets

<details><summary>👕 Fashion</summary>
<img width="400" alt="image" src="https://user-images.githubusercontent.com/11627845/157079335-8f36fc73-d826-4c0a-b1f3-ed5d650a1af1.png">
</details>

<details><summary>☢️ Chest X-Ray</summary>
<img src="https://user-images.githubusercontent.com/11627845/157067695-59851a77-5c43-4f68-80c4-403fec850776.png" width="400">
</details>
  
<details><summary>💰 NFT - bored apes</summary>
<img src="https://user-images.githubusercontent.com/11627845/157019002-573cc101-e23b-4020-825c-f37ec66c6ccf.jpeg" width="400">
</details>
  
<details><summary>🖼 Art</summary>
<img width="400" alt="image" src="https://user-images.githubusercontent.com/11627845/157074453-721c0f2d-3f7d-4839-b6ff-bbccbdba2e5f.png">
</details>
  
<details><summary>🚗 Cars</summary>
<img width="400" alt="image" src="https://user-images.githubusercontent.com/11627845/157081047-792df6bd-544d-420c-b180-df824c802e73.png">
</details>
  
<details><summary>🏞 Street view</summary>
<img width="400" alt="image" src="https://user-images.githubusercontent.com/11627845/157087532-46ae36a2-c97f-45d7-9c3e-c624dcf6dc46.png">
</details>

<details><summary>🦆 Birds</summary>
<img width="400" alt="image" src="https://user-images.githubusercontent.com/11627845/157069954-615a5cb6-dda0-4a2f-9442-ea807ad4a8d5.png">
</details>

<!-- end elevator-pitch -->

