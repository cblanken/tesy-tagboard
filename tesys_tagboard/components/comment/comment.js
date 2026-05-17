(function () { // Self invoking function to avoid variable clashing

  const setup_comment = (comment) => {
    const comment_body = comment.querySelector(".comment-body");
    const comment_text = comment.querySelector(".comment-text");
    const comment_edit_form = comment.querySelector(".comment-edit-form");
    const comment_edit_mode_form = comment.querySelector(".comment-edit-mode-form");
    const comment_edit_form_textarea = comment_edit_form.querySelector("textarea");
    const comment_id = comment.dataset?.comment;
    const comment_edit_confirm_btn = document.querySelector(`#comment-confirm-btn-${comment_id}`);
    const comment_edit_cancel_btn = document.querySelector(`#comment-cancel-btn-${comment_id}`);

    // Set textarea cursor to last position
    comment_edit_form_textarea.selectionStart = comment_edit_form_textarea.textContent.length
    comment_edit_form_textarea.selectionEnd = comment_edit_form_textarea.textContent.length

    // Swap readonly comment text for editable field
    function swapCommentEditField(enable) {
      if (enable) {
        comment_edit_form.classList.remove("hidden");
        comment_text.classList.add("hidden");
        comment_edit_form_textarea.focus();
      } else {
        comment_edit_form.classList.add("hidden");
        comment_text.classList.remove("hidden");
      }
    }

    comment_edit_form_textarea.addEventListener("input", e => {
      // Enable comment confirm and cancel buttons
      comment_edit_confirm_btn.classList.remove("btn-disabled");
      comment_edit_cancel_btn.classList.remove("btn-disabled");
    });

    // Show more/less comment text
    const show_more_btn = comment.querySelector(".show-more-btn")
    let showing_full_comment = false;
    const show_more_classes = ["min-h-fit", "bg-none"];
    const show_less_classes = ["bg-clip-text", "text-transparent"];
    function toggleShowMoreLess() {
      if (showing_full_comment) {
        comment_body.classList.add(...show_less_classes);
        comment_body.classList.remove(...show_more_classes);
        show_more_btn.textContent = "Show more";
      } else {
        comment_body.classList.add(...show_more_classes);
        comment_body.classList.remove(...show_less_classes);
        show_more_btn.textContent = "Show less";
      }
      showing_full_comment = !showing_full_comment;
    }
    show_more_btn.addEventListener("click", e => {
      toggleShowMoreLess(showing_full_comment)
    });
    let sm_media_width = window.getComputedStyle(comment).getPropertyValue('--breakpoint-sm');
    let sm_media_query = window.matchMedia(`(min-width: ${sm_media_width})`)
    if (!sm_media_query.matches && comment_body.scrollHeight !== comment_body.clientHeight) {
      show_more_btn.classList.remove("invisible");
    } else if (!sm_media_query.matches) {
      comment_body.classList.add(...show_more_classes);
      comment_body.classList.remove(...show_less_classes);
    }

    if (comment_edit_mode_form) {
      const comment_edit_cancel_btn = comment_edit_form.querySelector(".btn.comment-edit-cancel");
      const checkbox = comment_edit_mode_form.querySelector("input[type='checkbox']");

      comment_edit_cancel_btn.addEventListener("click", e => {
        checkbox.checked = false;
        swapCommentEditField(false)
      });

      // Toggle comment editable textarea
      checkbox.addEventListener("change", e => {
        swapCommentEditField(checkbox.checked);
      });

      // The label is styled as a button, but doesn't propgate change event
      // of the related input without manually dispatching the event.
      comment_edit_mode_form.querySelector("label").addEventListener("click", e => {
        checkbox.dispatchEvent(new Event("change"));
      });
    }
  };

  const setup = (comments) => {
    comments.forEach(comment => {
      setup_comment(comment);
    });
  };

  const get_comments = () => {
    return document.querySelectorAll("[data-comment]");
  }

  let comments = get_comments();
  setup(comments);

  document.addEventListener("htmx:after:request", e => {
    // Re-setup comment event listeners when an edit is made
    // TODO: target only edited comment instead of running setup over all comments
    let comments = get_comments();
    setup(comments);
  });
})();
