# Guide to loading your data

## Input Formats

When deploying your search app, you will be asked to select the input format of your data. 
This is the format of the data that you will be sending to the API. 
We currently support the following input formats for your custom input: DocumentArray, local path or S3 bucket.
In this section, we will explain each of these options in more detail.

### DocumentArray
If you have loaded your data as a `DocumentArray`, this option is perfect for you. In this case, you can simply provide
the name of your `DocumentArray` as the input. For example, if you have a `DocumentArray` called `cat_pictures`, you can
simply provide `cat_pictures` as the input, which will automatically pull your dataset.

```commandline
? How do you want to provide input? (format: https://docarray.jina.ai/)  DocumentArray name (recommended)
? Please enter your DocumentArray name: cat_pictures
```

If you are using this `DocumentArray` option, please make sure to model your data using the `@dataclass` decorator from [docarray](https://docarray.jina.ai/datatypes/multimodal/).
This allows you to model nested and multi-modal data as follows:

```python
from docarray import dataclass
from docarray.typing import Image, Text


@dataclass
class Page:
    main_text: Text
    image: Image
    description: Text
```

In this dataclass model, we have a `Page` document that has three fields: `main_text`, `image` and `description`. 
You can instantiate the dataclass model with your actual data, and cast it to a `Document` as follows:

```python
from docarray import Document, DocumentArray

page = Page(
    main_text='Hello world',
    image='apple.png',
    description='This is the image of an apple',
)

doc = Document(page)
da = DocumentArray([doc])
da.push(name="my_pages")
```

In the above example, we instantiate a `Page` document with some dummy data, and then cast it to a `Document`,
and finally add it to a `DocumentArray` which we can push to Jina Cloud under the name "my_pages".
This is the same name that we will use when deploying our search app with NOW.

More information about how to create and push your own `DocumentArray` can be found [here](https://docarray.jina.ai/).

### Local Folder
If you have your data stored locally, you can provide the path to the folder containing your data.
The folder should contain all files that you want to index.

Here is an example of a folder structure for text-to-image search:
```
usr
├── data
│   ├── images
│   │   ├── 1.jpg
│   │   ├── 2.jpg
│   │   ├── 3.jpg
│   │   ├── 4.jpg
```
In this case, the local path you should provide is `/usr/data/images`, as follows:

```commandline
? How do you want to provide input? (format: https://docarray.jina.ai/)  Local folder
? Please enter your local path: /usr/data/images
```

### AWS S3 bucket
If you have your data stored in an AWS S3 bucket, you can provide the S3 URI, your `AWS access key ID` and `AWS secret key`.
Similar to the local folder option, the S3 bucket should contain all files that you want to index.
The only difference is that the S3 Uri should be in the following format: `s3://<bucket-name>/<path-to-data>`.
Taking the example structure from above, the S3 URI would be `s3://my-<bucket-name>/usr/data/images`.

Here is an example of what your interaction may look like in the CLI:

```commandline
? How do you want to provide input? (format: https://docarray.jina.ai/)  S3 bucket
? Please enter the S3 URI to the folder:  s3://<bucket-name>/<path-to-data>
? Please enter the AWS access key ID:  <my-key-id>
? Please enter the AWS secret access key:  <my-access-key>
? Please enter the AWS region:  <my-region>
```


## Support for Tags
For most professional applications, you will want to provide additional information about your data, such as price, creator, brand, etc.
This information can be provided in the `tags` of your `Document`s in case you selected the `DocumentArray` option.
If you selected the `local folder` or `S3 bucket` option, you can provide this information in a `json` file for each document.
The example from above would look like this:
```
root
├── data
│   ├── images
│   │   ├── 1
│   │   │   ├── 1.jpg
│   │   │   ├── 1.json
│   │   ├── 2
│   │   │   ├── 2.jpg
│   │   │   ├── 2.json
│   │   ├── 3
│   │   │   ├── 3.jpg
│   │   │   ├── 3.json
│   │   ├── 4 
│   │   │   ├── 4.jpg
│   │   │   ├── 4.json
```
The `json` file should contain the `tags` of the `Document` in the following format:
```
{
    "price": 100,
    "brand": "Jina"
}
```


## Supported File Formats
Here is an overview of the supported file formats for each modality:

- Text: `.txt` (can also have a different extension, but has to be plain text)
- Image: `.jpg`, `.png`, ... (everything supported by `PIL`)
- Audio: `.wav`, `.mp3`, ... (everything supported by `librosa`)
- Video: `.gif` 

## Search and filter fields

Once you have chosen your input type and ensured that your data is in the correct format, you will be asked to select
the fields from your dataset that you want to search and filter on. NOW will automatically detect these fields for you,
and list them for you to choose from. You can select only one field for searching. Here's an example using the `birds`
demo dataset:

```commandline
? How do you want to provide input? (format: https://docarray.jina.ai/)  Demo dataset
? What demo dataset do you want to use?  🦆 birds (≈12K docs)
? Please select the index fields:  (<up>, <down> to move, <space> to select, <a> to toggle, <i> to invert)
 ○ label
❯○ image
? Please select the filter fields  (<up>, <down> to move, <space> to select, <a> to toggle, <i> to invert)
❯◯ label
```

In the above commandline interaction, we have selected the `birds` dataset, and we can see that the `label` and `image`
fields are available for us to search on. We have selected the `image` field for searching, and the `label` field for
filtering.

## Next steps

Now that you have selected your input format and the fields you want to search and filter on, you can move on to the next step,
where you will be asked to choose a name for your search app and whether you want to secure your application. 
