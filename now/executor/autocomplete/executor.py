import json
import os
from typing import Optional

from better_profanity import profanity
from docarray import DocumentArray
from fast_autocomplete import AutoComplete

from now.executor.abstract.auth.auth import NOWAuthExecutor as Executor
from now.executor.abstract.auth.auth import SecurityLevel, secure_request


class NOWAutoCompleteExecutor(Executor):
    def __init__(self, search_traversal_paths: str = '@r', words=None, *args, **kwargs):
        self.words = words if words else {}
        self.search_traversal_paths = search_traversal_paths
        self.autocomplete = None
        self.char_threshhold = 100

        super().__init__(*args, **kwargs)

        self.words_path = (
            os.path.join(self.workspace, 'words.json') if self.workspace else None
        )
        if self.words_path and os.path.exists(self.words_path):
            with open(self.words_path, 'r') as fp:
                self.words = json.load(fp)
                self.autocomplete = AutoComplete(words=self.words)

    def update_save_words(self, word):
        """
        Method to update word count dictionary and dumps new dictionary
        """
        if word in self.words:
            self.words[word]['count'] += 1
        else:
            self.words[word] = {'count': 1}
        if self.words_path:
            with open(self.words_path, 'w') as fp:
                json.dump(self.words, fp)

    @secure_request(on='/search', level=SecurityLevel.USER)
    def search_update(
        self, docs: Optional[DocumentArray] = None, parameters: dict = {}, **kwargs
    ):
        traversal_paths = parameters.get('traversal_paths', self.search_traversal_paths)
        flat_docs = docs[traversal_paths]

        for doc in flat_docs:
            if doc.text and not profanity.contains_profanity(doc.text):
                search_words = doc.text.split(' ')
                # prevent users from misusing API
                if len(doc.text) < self.char_threshhold:
                    # in case query is composed of two words
                    for word in search_words:
                        self.update_save_words(word)
                    # add bigram and tri gram suggestions
                    if len(search_words) == 2 or len(search_words) == 3:
                        self.update_save_words(doc.text)

        self.auto_complete = AutoComplete(words=self.words)
        return docs

    @secure_request(on='/suggestion', level=SecurityLevel.USER)
    def get_suggestion(
        self, docs: Optional[DocumentArray] = None, parameters: dict = {}, **kwargs
    ):
        if len(docs) and docs[0].text:
            docs[0].tags['suggestions'] = self.auto_complete.search(
                docs[0].text, max_cost=3, size=5
            )
            return docs
        return