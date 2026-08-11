class crm_action:
    def __call__(self, fn):
        self.fn = fn
        self.fn._crm_action = True
        self.fn.verbose_name = self.verbose_name
        return fn

    def __init__(self, verbose_name=None):
        self.verbose_name = verbose_name
