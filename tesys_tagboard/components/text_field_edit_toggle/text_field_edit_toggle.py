from django_components import Component, register


@register("text_field_edit_toggle")
class TextFieldEditToggleComponent(Component):
    template_file = "text_field_edit_toggle.html"
    js_file = "text_field_edit_toggle.js"

    def get_template_data(self, args, kwargs, slots, context):
        text = kwargs.get("text")
        toggle_btn_text = kwargs.get("toggle_btn_text")
        empty_text = kwargs.get("empty_text")
        edit_url = kwargs.get("edit_url")
        input_name = kwargs.get("input_name")
        is_link = kwargs.get("is_link")
        return {
            "text": text,
            "toggle_text": toggle_btn_text,
            "empty_text": empty_text,
            "edit_url": edit_url,
            "input_name": input_name,
            "is_link": is_link,
        }
