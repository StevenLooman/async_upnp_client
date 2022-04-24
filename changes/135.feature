Always use CaseInsensitiveDict for headers (@bdraco)

Headers were typed to not always be a CaseInsensitiveDict but
in practice they always were. By ensuring they are always a
CaseInsensitiveDict we can reduce the number of string
transforms since we already know when strings have been
lowercased.
