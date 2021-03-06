from django.contrib.contenttypes.models import ContentType
from django.db.models import Q

from mpttmenu.models import MenuNode
from mpttmenu.utils import MenuCache

MENU_MAX_LEVEL = 64


class MenuProcessor(object):
    """
    This class is used to build the menu tree from the context
    its goal is to remove the logic from the template
    """
    def __init__(self, context, level_min=0, level_max=MENU_MAX_LEVEL, **kwargs):
        self.context = context

        self.object_passed = 'object' in kwargs
        self.object = kwargs.get('object', None)
        self.node = None
        self.level_min = level_min
        self.level_max = level_max
        self.cache = MenuCache()

        self.determine_object_from_context()
        self.determine_node_from_object()

    ############## OVERRIDABLE METHODS #############
    def determine_object_from_context(self):
        """
        Attempt to find the current object from the datas we have
        It is recommanded to pass the object parameter whenever possible (always!) to avoid some useless queries
        or to override this method to match your code/logic
        """
        if not self.object_passed:
            self.object = self.object or self.context.get('object', None)  # could be dangerous if object is not used in the default way
            if not self.object:
                # is there a better way to do this ? with resolve ?
                try:
                    path = self.context['view'].request.path
                except (KeyError, AttributeError):
                    # in case of django < 1.5
                    path = self.context['request_path']

                l = [m for m in MenuNode.tree.all() if m.content_object.get_absolute_url() == path]
                if l:
                    self.node = l[0]  # avoid doing anything in determine_node_from_object if possible
                    self.object = self.object.content_object

    def determine_node_from_object(self):
        """
        If you can afford to change the referenced model,
        you can add 'menu_node = generic.GenericRelation(MenuNode)' to your model
        This allow to retrieve the node by doing self.object.menu_node
        see : https://docs.djangoproject.com/en/dev/ref/contrib/contenttypes/#s-reverse-generic-relations
        """
        if self.node or not self.object:
            return
        else:
            if hasattr(self.object, 'menu_node'):
                # This is a generic FOREIGN KEY, so it is safe to do a simple get()
                self.node = self.object.menu_node.get()
            else:
                self.node = MenuNode.tree.get(content_type=ContentType.objects.get_for_model(self.object.__class__),
                                              object_id=self.object.id)

    def determine_tree(self):
        """
        This method should return a queryset of nodes that will be displayed
        the default implementation shows the full tree,
        but you can override this to use one of the convenient _get_*_nodes() methods, or make your own
        """
        return self._get_all_nodes()

    def get_default_tree(self):
        """
        This what is returned in case there is no object found
        (for pages not present in the menu)
        """
        return self._get_all_nodes()

    ################################################

    def get_nodes(self):
        nodes = self.cache[self.object]
        if not nodes:
            try:
                nodes = self.determine_tree()
            except AttributeError:
                # we have no node, we are probably in a page not present in the menu
                # let's use the fallback
                nodes = self.get_default_tree()

            nodes = nodes.filter(level__range=[self.level_min, self.level_max]).select_related('parent', 'content_object')
            self.cache[self.object] = nodes
        return nodes

    ################# convenient methods ################
    # note : children are only level+1

    def _get_all_nodes(self):
        return MenuNode.tree.all()

    def _get_root_nodes(self):
        return MenuNode.tree.root_nodes()

    def _get_branch_nodes(self):
        return self.node.get_root().get_descendants(include_self=True)

    def _get_root_and_branch_nodes(self):
        return MenuNode.tree.filter(Q(level=0) | Q(id__in=self.node.get_root().get_descendants().values_list('id', flat=True)))

    def _get_root_and_sibblings_nodes(self):
        return MenuNode.tree.filter(Q(level=0) | Q(parent=self.node.parent))

    def _get_root_and_children_nodes(self):
        return MenuNode.tree.filter(Q(level=0) | Q(parent=self.node))

    def _get_children_nodes(self):
        return self.node.children.all()

    def _get_ancestors_nodes(self):
        return self.node.get_ancestors()

    def _get_descendants_nodes(self):
        return self.node.get_descendants()
