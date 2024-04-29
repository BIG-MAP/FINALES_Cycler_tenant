# FINALES_Cycler_tenant

The Cycler tenant created for the use with FINALES.

# Related Documents and Links to FINALES

Documents related to this project and its broader context can be found on the respective Wiki page of this project: [https://github.com/BIG-MAP/FINALES2/wiki/Links](https://github.com/BIG-MAP/FINALES2/wiki/Links)

Links to FINALES:

1. FINALES 2 latest version Github
[https://github.com/BIG-MAP/FINALES2](https://github.com/BIG-MAP/FINALES2)

1. FINALES 2 used Version Zenodo
[10.5281/zenodo.10987727](10.5281/zenodo.10987727)

1. Schemas of FINALES 2
[https://github.com/BIG-MAP/FINALES2_schemas](https://github.com/BIG-MAP/FINALES2_schemas)


# Description

The Cycler tenant handels the reservation of channels, as well as the start, export and smaller analysis of the cycling data.
When handling a reservation request, the cycler creates a uuid as reservation id, writes this id to free marked channels in a seperate json file, therefore marks the channels as reserved and returns the reservation id.
Upon handling a cycle request the tenant checks for the first channel having the input reservation id, creates a predefined cycling protocol for the channel and starts the channel. The request as well as start time and an esitmated time for the export after 40 cycles is as well saved in the seperate json file.
In addition to the checks for new requests, it constantly checks if the export time of one channel is reached and triggers the export. The analysis on a seperate small server is then triggerd with the data and results are posted to FINALES.

# Warning
Some of the code is based on AutoHotKey using your mouse and keyboard. Before using it the realative positions must be corrected for your screen.


## Acknowledgements

This project received funding from the European Union’s Horizon 2020 research and innovation program under grant agreement no. 957189 (BIG-MAP).
The authors acknowledge BATTERY2030PLUS, funded by the European Union’s Horizon 2020 research and innovation program under grant agreement no. 957213.
This work contributes to the research performed at CELEST (Center for Electrochemical Energy Storage Ulm-Karlsruhe) and was co-funded by the German Research Foundation (DFG) under Project ID 390874152 (POLiS Cluster of Excellence).# ArbinServer-V2
 
