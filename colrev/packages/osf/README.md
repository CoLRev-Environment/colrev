# Open Science Framework(OSF) Search Source
 
### API search
 
ℹ️ Restriction: API searches do not support complex queries yet.
 
Download search results and store in `data/search/` directory.
 
Data from the OSF open platform can be retrieved with the URL from the [https://www.osf.io/](https://api.osf.io/v2/nodes/?filter). Add the URL as follows:
 
```
colrev search --add colrev.osf -p "https://api.osf.io/v2/nodes/?filter[title]=reproducibility"
```
 
The retrieved data, including detailed project metadata and resources, is processed and made available for further actions within CoLRev, such as analysis or reporting.
 
It is not necessary to pass an API key as a parameter here. In order to keep the key secret, you will be prompted to enter it through user input if it is not already stored in the settings. The api key can be requested via the [OSF settings page](https://accounts.osf.io/login?service=https://osf.io/settings/tokens/).
 
The search can be filtered by changing the filter parameter to one of the following parameters: title, id, type, category, year, description, tags, data_created. For each of these, change "filter[parameter]=value" in the URL.
 
```
colrev search --add colrev.osf -p "https://api.osf.io/v2/nodes/?filter[description]=machine%20learning"
```
 
## Links
 
- [OSF](https://osf.io/)
- [OSF_API](https://developer.osf.io/)
