class MultipleMatches(Exception):
    def __init__(self, detail):
        super(Exception, self).__init__(detail)

class IdCollision(Exception):
    def __init__(self, detail):
        super(Exception, self).__init__(detail)
