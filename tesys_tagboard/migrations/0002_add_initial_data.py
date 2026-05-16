from django.contrib.auth.management import create_permissions
from django.db import migrations
from django.db.models import Model

def migrate_permissions(apps, schema_editor):
    # Ensure auth app creates default permissions
    for app_config in apps.get_app_configs():
        app_config.models_module = True
        create_permissions(app_config, apps=apps, verbosity=0)
        app_config.models_module = None


def add_default_groups(apps, schema_editor):
    # Create default groups and set permissions
    Group = apps.get_model("auth.Group")
    Permission = apps.get_model("auth.Permission")
    user_group = Group(id=1, name="Users")
    user_permissions = Permission.objects.filter(codename__in=[
        "add_audio",
        "add_collection",
        "add_comment",
        "add_favorite",
        "add_image",
        "add_post",
        "add_tag",
        "add_video",
        "delete_favorite",
        "view_artist",
        "view_audio",
        "view_collection",
        "view_comment",
        "view_favorite",
        "view_image",
        "view_post",
        "view_tag",
        "view_tagalias",
        "view_video",
        # Custom perms
        "add_post_to_collection",
        "remove_post_from_collection",
    ])
    user_group.save()
    user_group.permissions.set(user_permissions)

    mod_group = Group(id=2, name="Moderators")
    mod_permissions = Permission.objects.filter(codename__in=[
        # Default Django model perms
        "add_artist",
        "add_audio",
        "add_collection",
        "add_comment",
        "add_favorite",
        "add_image",
        "add_post",
        "add_tag",
        "add_tagalias",
        "add_video",
        "change_artist",
        "change_collection",
        "change_post",
        "change_tag",
        "change_tagalias",
        "delete_artist",
        "delete_audio",
        "delete_collection",
        "delete_favorite",
        "delete_image",
        "delete_post",
        "delete_tag",
        "delete_tagalias",
        "delete_video",
        "view_artist",
        "view_audio",
        "view_collection",
        "view_comment",
        "view_favorite",
        "view_group",
        "view_image",
        "view_post",
        "view_tag",
        "view_tagalias",
        "view_video",
        # Custom perms
        "lock_comments",
        "add_post_to_collection",
        "remove_post_from_collection",
    ])
    mod_group.save()
    mod_group.permissions.set(mod_permissions)


def add_categories(apps, schema_editor):
    TagCategory = apps.get_model("tesys_tagboard.TagCategory")
    TagCategory(name="artist", light_bg="#bae1ff", dark_bg="#315f82").save()
    TagCategory(name="copyright", light_bg="#ffd3b6", dark_bg="#855b3f").save()


class Migration(migrations.Migration):
    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"), # ensure auth migrations have run
        ('tesys_tagboard', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(migrate_permissions),
        migrations.RunPython(add_default_groups),
        migrations.RunPython(add_categories),
    ]
