Reduce string conversion in CaseInsensitiveDict lookups (@bdraco)

`get` was previously provided by the parent class which
had to raise KeyError for missing values. Since try/except
is only cheap for the non-exception case the performance
was not good when the key was missing.

Similar to python/cpython#106665
but in the HA case we call this even more frequently.
