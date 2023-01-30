import itertools
import json
import os
from typing import Optional

from better_profanity import profanity
from docarray import DocumentArray
from fast_autocomplete import AutoComplete

from now.executor.abstract.auth.auth import (
    SecurityLevel,
    get_auth_executor_class,
    secure_request,
)

Executor = get_auth_executor_class()


class NOWAutoCompleteExecutor2(Executor):
    def __init__(self, words=None, *args, **kwargs):
        self.words = words if words else {}
        self.autocomplete = None
        self.char_threshold = 100

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
        Method to update word count dictionary and dumps new dictionary.
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
        for doc in docs['@c']:
            if doc.text and not profanity.contains_profanity(doc.text):
                search_words = doc.text.split(' ')
                # prevent users from misusing API
                if len(doc.text) < self.char_threshold:
                    # in case query is composed of two words
                    for word in search_words:
                        self.update_save_words(word)
                    # add bi-gram and tri-gram suggestions
                    if len(search_words) == 2 or len(search_words) == 3:
                        self.update_save_words(doc.text)

        self.auto_complete = AutoComplete(words=self.words)
        return docs

    @secure_request(on='/suggestion', level=SecurityLevel.USER)
    def get_suggestion(
        self, docs: Optional[DocumentArray] = None, parameters: dict = {}, **kwargs
    ):
        for doc in docs:
            doc.tags['suggestions'] = self.flatten_list(
                self.auto_complete.search(doc.text, max_cost=3, size=5)
            )
        return docs

    def flatten_list(self, regular_list):
        flat_list = list(itertools.chain(*regular_list))
        return flat_list
