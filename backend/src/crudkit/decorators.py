class crm_action:
    def __call__(self, fn):
        self.fn = fn
        self.fn._crm_action = True
        self.fn.verbose_name = self.verbose_name
        self.fn.requires_approval = self.requires_approval
        return fn

    def __init__(self, verbose_name=None, requires_approval=False):
        self.verbose_name = verbose_name
        # MCP clients and agents may only propose this action; a person confirms it.
        self.requires_approval = requires_approval
