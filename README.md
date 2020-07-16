## CLIPy, Campus Life Integration Platform wrapper
**In case you have no clue of what CLIP is then this package is not for you.**

This is a crawler which downloads relevant information from CLIP, as such it requires student credentials.
It does provide an interface (both programatic as wel as a webservice with REST endpoints) to lookup the crawled data.

Even if you're a student and have the all mighty credentials, it still isn't probably something you'll want to try.

If you're brave and want to try it, or want that information for something else (please don't be evil), it takes several days to fully bootstrap the database, and it's a somewhat error-prone process with a lot of disconnections along the way.

Avoid doing so during times that might disturb other students access to CLIP. This thing does several requests every second. 1AM-6AM(GMT) it's probably your best shot.



### Instalation
    pip install clip-crawler

### Usage
    from CLIPy import CacheStorage, Clip
    
    storage = CacheStorage.postgresql('username', 'password', 'schema')
    Clip.populate('CLIP ID', 'password', storage) # Run only once. Takes forever.
    
    clip = Clip(storage)
    [print(student) for student in clip.find_student("John Smith")]

### Stuff that this is able to retrieve
Right now, most of CLIP data.
- Students
- Teachers
- Classes (most of their information, student grades, turns, teachers)
- Departments
- Courses
- Files (with deduplication :) )
- Physical entities (buildings, classrooms, auditoriums, laboratories, ...)
- National access contest admissions
- Library occupied/spare rooms

### TODO
- Timespan filters (eg: crawl *[thing]* from 2015 to 2017)
- Evaluation dates
- Class summaries
- Course curricular plans (possibly impossible as CLIP does not expose CP rules)
- Better student course tagging