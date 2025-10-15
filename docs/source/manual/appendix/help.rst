Help
==================================

We are here to help you and others who may struggle with the same issues.
Here is how you can help us help you.

Identify the source
------------------------------

CoLRev uses many powerful libraries and data sources.
In addition, the particular setup of your local machine and CoLRev environment may prevent us from replicating issues.
We need your help in narrowing down the source of the issue by running the command with the ``--verbose`` option (e.g., ``colrev load --verbose``) to retrieve the full details and error trace (if any).

For example, this may help to identify:

- Errors in ``colrev load`` that are caused by the zotero translators
- Errors in ``colrev prep`` that may result from several metadata sources or preparation scripts.

Some operations offer dedicated debugging functionality, such as ``colrev prep -d RECORD_ID``, which can track down the scripts or data sources that introduced an error.

Create a minimum reproducible example
------------------------------------------

To solve issues efficiently, minimum reproducible examples are given priority. We also focus on bugs that occur in the latest version because CoLRev is developing quickly.

Check prior documentation and file the issue
----------------------------------------------

Please check prior issues in the `issue tracker <https://github.com/CoLRev-Environment/colrev/issues>`__ and run a quick Google search for possible solutions.

You can ask questions on `Stackoverflow <https://stackoverflow.com/questions>`_, using the colrev tag.

You can also file a bug report in the `issue tracker <https://github.com/CoLRev-Environment/colrev/issues>`__ or propose a solution by opening a pull request.

..
    FAQ

    add separate section "contribute": like https://www.tidyverse.org/contribute/#issues
