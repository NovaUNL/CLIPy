CLIPy
=====
Campus Life Integration Platform wrapper
****************************************

**In case you have no clue of what CLIP is then this package is not for you.**

This is a crawler which downloads relevant information from CLIP, as such it requires student credentials.
It does provide an interface to lookup the crawled data.

Even if you're a student and have the all mighty credentials, it still isn't probably something you'll want to try.

If you're brave and want to try it, or want that information for something else (please don't be evil), it takes several days to fully bootstrap the database, and it's a somewhat error-prone process with a lot of disconnections along the way.

Avoid doing so during times that might disturb other students access to CLIP. This thing does several requests every second. 1AM-6AM(GMT) it's probably your best shot.


The data is stored onto any database supported by SQLAlchemy.

This has just been ported to SQLAlchemy and it is **not even close to being optimized**. As such it still runs with a single session, with serial transactions.
Performance is bad when compared to the previous SQLite code, RAM consumption is atrocious.

`Repository <https://gitlab.com/claudiop/CLIPy>`_
