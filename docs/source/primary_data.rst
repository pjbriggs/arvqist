Identify primary data files
===========================

SOLiD4 Data
***********

For SOLiD4 sequencing runs, the primary data are `csfasta`/`qual` file pairs. These
files may have been compressed (using either `bzip2` or `gzip`), and copies might
also exist. There might also be links to these files (with the same base name).

Use the `list_primary_data_for_solid.sh` script to get initial lists of primary
data files and links, e.g.::

    list_primary_data_for_solid.sh DIR

which produces two files called `primary_data.DIR` and `links.DIR`.

We use checksums to identify duplicate copies of files. Use the
`get_primary_data_checksums.sh` to get a list of primary data files and their MD5
checksums, e.g.::

    get_primary_data_checksums.sh DIR primary_data.DIR > DIR.md5s

Note that for compressed files, the checksums that are generated are actually for
the uncompressed versions.

(This can be computationally intensive so it should be submitted to the appropriate
job submission system.)

Identify duplicated files
*************************

To identify duplicates, use the `list_duplicated_checksums.sh` script e.g.::

    list_duplicated_checksums.sh DIR.md5s [DIR2.md5s ...]

To look at the targets for links, send the list of links from the
`list_primary_data_for_solid.sh` into the `list_links_and_targets.sh` script, e.g.::

    list_links_and_targets.sh DIR links.DIR
