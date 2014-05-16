#hdbits.org

import string, os

HDBITS_MAIN = "https://hdbits.org/"
HDBITS_SEARCH_PAGE = "https://hdbits.org/dox.php?%s=1&search=%s"
HDBITS_LOGIN_PAGE = 'https://hdbits.org/login.php'
HDBITS_LOGON_PAGE = 'https://hdbits.org/login/doLogin'
OS_PLEX_USERAGENT = 'plexapp.com v9.0'
subtitleExt       = ['utf','utf8','utf-8','sub','srt','smi','rt','ssa','aqt','jss','ass','idx']

langPrefs2HDbits = {'eng':'uk', 'swe':'se', 'ara':'ar', 'bul':'bg', 'chi':'cn', 'hrv':'hr', 'cze':'cz', 'dan':'dk', 'dut':'nl', 'est':'ee', 'fin':'fi', 'fre':'fr', 'ger':'de', 'gre':'gr', 'heb':'il', 'hun':'hu', 'ita':'it', 'jpn':'jp', 'kor':'kr', 'nor':'no', 'pol':'pl', 'por':'pt', 'ron':'ro', 'rus':'ru', 'srp':'cs', 'slo':'sk', 'slv':'si', 'spa':'es', 'tur':'tr'}

#Find these in the DefaultPrefs.json and http://dev.plexapp.com/docs/api/localekit.html#locale-language
langPrefs2Plex = {'eng':'en', 'swe':'sv', 'ara':'ar', 'bul':'bg', 'chi':'zh', 'hrv':'hr', 'cze':'cs', 'dan':'da', 'dut':'nl', 'est':'et', 'fin':'fi', 'fre':'fr', 'ger':'de', 'gre':'el', 'heb':'he', 'hun':'hu', 'ita':'it', 'jpn':'ja', 'kor':'ko', 'nor':'no', 'pol':'pl', 'por':'pt', 'ron':'ro', 'rus':'ru', 'srp':'sr', 'slo':'sk', 'slv':'sl', 'spa':'es', 'tur':'tr'}

class SubInfo():
    def __init__(self, lang, url, sub, name):
        self.lang = lang
        self.url = url
        self.sub = sub
        self.name = name
        self.ext = string.split(self.name, '.')[-1]

def Start():
    HTTP.CacheTime = 0
    HTTP.Headers['User-agent'] = OS_PLEX_USERAGENT
    Log("START CALLED")

def checkLogin():
    Log("checkLogin")
#TODO: Instead of trusting the server to redirect us to the login page if we're not logged in. Check for the cookie
    #instead with HTTP.GetCookiesForURL(url)?

    elem = HTML.ElementFromURL(HDBITS_MAIN)
    lols = elem.xpath("//form//input[@name='lol']/@value")
    Log("lols %s" % lols)

    if len(lols) == 1:
        lol = str(lols[0])
        values = {'uname':Prefs['username'],'password':Prefs['password'],'lol':lol}
        elem2 = HTML.ElementFromURL(HDBITS_LOGON_PAGE, values=values)
        svar1 = HTML.StringFromElement(elem2)

#Prepare a list of languages we want subs for
def getLangList():
    langList = [Prefs["langPref1"]]
    if(Prefs["langPref2"] != "None"):
        langList.append(Prefs["langPref2"])

    return langList

def getSnEString(season, episode):
    return "S" + str(season).zfill(2) + "E" + str(episode).zfill(2)

#Do a basic search for the filename and return all sub urls found
def simpleSearch(searchString, lang = 'eng'):
#First make sure we are logged in
    checkLogin() 
    
    Log("Searching for: %s" % searchString)
    urlName = String.Quote(searchString, usePlus=True)
    Log("escaped: %s" % urlName)
    searchUrl = HDBITS_SEARCH_PAGE % (langPrefs2HDbits[lang], urlName)
    Log("searchUrl: %s" % searchUrl)
    elem = HTML.ElementFromURL(searchUrl)

#Find all sub urls on this page and return the link/url to them
    subtitles = elem.xpath("//a[starts-with(@href,'getdox.php')]/@href")
    for subtitle in subtitles:
        Log("Subtitle: %s" % subtitle)

    return subtitles

def getReleaseGroup(filename, override = False):
    if(Prefs["UseReleaseGroup"] == True or override == True):
        tmpFile = string.replace(filename, '-', '.')
        splitName = string.split(tmpFile, '.')
        group = splitName[-2]
        return group
    else:
        return ""

def getSubsForPart(searchString):
    Log("SearchString: %s" % searchString)
#For each language defined in preferences, do a search
    subsList = []
    for lang in getLangList():
        plexLang = Locale.Language.Match(langPrefs2Plex[lang])
        Log("LangTest: %s" % plexLang)
        subtitleUrls = simpleSearch(searchString, lang)
#For each sub found. Fetch it and hand it over to Plex with the right language and suffix set
        for url in subtitleUrls:
            splitUrl = string.split(url, '/')
            splitUrl[-1] = String.Quote(splitUrl[-1], usePlus=True)
            url = string.join(splitUrl, '/')
            subUrl = HDBITS_MAIN + url
            subExt = string.split(url, '.')[-1] #Find suffix for this sub type
            Log("SubUrl: %s" % subUrl)
            Log("SubExt: %s" % subExt)
            if subExt in subtitleExt:
                Log("subExt %s is ok" % subExt)
                sub = HTTP.Request(subUrl, immediate=True).content
                si = SubInfo(plexLang, subUrl, sub, subUrl)
                subsList.append(si)
            elif subExt == "zip":
                zipArchive = Archive.ZipFromURL(subUrl)
                for name in zipArchive:
                    Log("Name in zip: %s" % name)
                    subData = zipArchive[name]
                    si = SubInfo(lang, subUrl, subData, name)
                    subsList.append(si)
            else:
                Log("Can't handle sub of type: %s" % subExt)
    return subsList

class HdbitsSubtitlesAgentMovies(Agent.Movies):
    name = 'HDBits.org Movie Subtitles'
    languages = [Locale.Language.English]
    primary_provider = False
    contributes_to = ['com.plexapp.agents.imdb']

    def getMovieSearchString(self, fileName):
        Log("getMovieSearchString, fileName: %s" % fileName)
        releaseGroup = getReleaseGroup(fileName, True)
        #Prepare the filename for search by removing the suffix and other nuisances
        lastDotIndex = string.rfind(fileName, '.')
        if(lastDotIndex > -1):
            searchString = fileName[0:lastDotIndex]
    
        Log("ReleaseGroup: %s" % releaseGroup)
        searchString = string.replace(searchString, releaseGroup, "")
        
        searchString = string.replace(searchString, '.', ' ')
        searchString = string.replace(searchString, '(',' ')
        searchString = string.replace(searchString, ')',' ')
        searchString = string.replace(searchString, '-',' ')
        
        searchString = searchString + getReleaseGroup(fileName)
        
        return searchString.strip() 

    def search(self, results, media, lang):
        Log("MOVIE SEARCH CALLED")    
        results.Append(MetadataSearchResult(id = 'null', score = 100))

    def update(self, metadata, media, lang):
            Log("MOVIE UPDATE CALLED")
            for item in media.items:
                for part in item.parts:
                    subsList = getSubsForPart(self.getMovieSearchString(os.path.basename(part.file)))
                    for si in subsList:
                        part.subtitles[si.lang][si.url] = Proxy.Media(si.sub, ext=si.ext)


class HdbitsSubtitlesAgentMovies(Agent.TV_Shows):
    name = 'HDBits.org TV Subtitles'
    languages = [Locale.Language.English]
    primary_provider = False
    contributes_to = ['com.plexapp.agents.thetvdb']

    def search(self, results, media, lang):
        Log("TV SEARCH CALLED")    
        results.Append(MetadataSearchResult(id = 'null', score = 100))

    def update(self, metadata, media, lang):
        Log("TvUpdate. Lang %s" % lang)
        for season in media.seasons:
            for episode in media.seasons[season].episodes:
                for item in media.seasons[season].episodes[episode].items:
                    for part in item.parts:
                        searchWords = [media.title, getSnEString(season, episode), getReleaseGroup(part.file)]
                        searchString = string.join(searchWords, ' ').strip()
                        subsList = getSubsForPart(searchString)
                        Log("Found %d subs" % len(subsList))
                        for si in subsList:
                            part.subtitles[si.lang][si.url] = Proxy.Media(si.sub, ext=si.ext)
