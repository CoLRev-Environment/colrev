first search: GS, "digital labour market" (2018)
second search: GS, "digital labour market" (2020)
third search: WoS, "digital labour market" (2021)

-> include hash of (author+year+journal+issue+volume+pages) in the gathered bib file
- this solves the trace-of-evidence problem (it must be possible to change entries (e.g., merging, completing, correcting), but it must also be possible to trace the updated entries to the exact source)
- solution: never change the source (raw data!), but when including the hash, it is possible to change all fields (including the ID, which may be duplicated across searches or search updates)
- problem of search-assigned unique-ids: they differ/are not identical across search updates/associated with the identical record (e.g., publish-or-perish exports of google scholar, which are just the numbers of results lists that are included as the "unique id")
-> have to assume that sources have imperfect quality (instability over time, incompleteness, incorrectness)

-> acknowledge that hash-ids are identical if their base-string (author+title+year+journal+...) is identical (even when it originates from different sources!) - that is not a problem since it does not inadequately match records (only if they are completely identical) (we could refer to this as "merging perfect matches by design"), but it shows that the number of duplicates cannot be determined based on hash-ids!


-> hash-ids: similarity to children in a git-merge process!
-> partial hash! robust wrt. to frequently changing fields (e.g., nr of citations/visits)
-> create function to identify the original record based on its hash?



-> check which fields are considered in the jabref-duplicate matching procedures!
https://docs.jabref.org/finding-sorting-and-cleaning-entries/findduplicates
https://github.com/JabRef/jabref/blob/c06966d9c16eb9302893b36c6d3a74c036f1260b/src/main/java/org/jabref/logic/database/DuplicateCheck.java#L307



Advantage of hash-ids: All other fields in the merged bib database can be updated/corrected without breaking the link to the original source.
should hash-id be comma-separated?

NEXT thing to figure out: how to concatenate (comma-separate) hash-ids when merging entries (Jabref suggests to select one or the other)
