<competition-participation>
  <form class="ui form">
    <div class="field required">
      <label>Terms</label>
      <textarea class="markdown-editor" ref="terms" name="terms"></textarea>
    </div>

    <div class="field">
      <div class="ui checkbox">
        <input
          selenium="auto-approve"
          type="checkbox"
          name="registration_auto_approve"
          ref="registration_auto_approve"
          onchange="{form_updated}"
        />
        <label>
          Auto approve registration requests
          <span
            data-tooltip="If left unchecked, registration requests must be manually approved by the benchmark creator or collaborators"
            data-inverted=""
            data-position="bottom center"
          >
            <i class="help icon circle"></i>
          </span>
        </label>
      </div>
    </div>

    <div class="field">
      <div class="ui checkbox">
        <input
          type="checkbox"
          name="allow_robot_submissions"
          ref="allow_robot_submissions"
          onchange="{form_updated}"
        />
        <label>
          Allow robot submissions
          <span
            data-tooltip="If left unchecked, robot users will have to be manually approved by the benchmark creator or collaborators. This can be changed later."
            data-inverted=""
            data-position="bottom center"
          >
            <i class="help icon circle"></i>
          </span>
        </label>
      </div>
    </div>

    <div class="field">
      <label>Whitelist Emails</label>
      <p>
        A list of emails (one per line) of users who do not require competition
        organizer's approval to enter this competition.
      </p>
      <div class="ui yellow message">
        <span><b>Note:</b></span><br />
        Only valid emails are allowed<br />
        Empty lines are not allowed
      </div>
      <textarea
        class="markdown-editor"
        ref="whitelist_emails"
        name="whitelist_emails"
      ></textarea>
      <div class="error-message" style="color: red;"></div>
    </div>
  </form>

  <script>
    let self = this;

    self.data = {};

    self.on("mount", () => {
      self.markdown_editor = create_easyMDE(self.refs.terms);
      self.markdown_editor_whitelist = create_easyMDE(
        self.refs.whitelist_emails,
        false,
        false,
        "200px"
      );

      if ($ && $.fn && $.fn.checkbox) {
        $(".ui.checkbox", self.root).checkbox();
      }

      $(":input", self.root)
        .not('[type="file"]')
        .not("button")
        .not("[readonly]")
        .each(function () {
          this.addEventListener("keyup", self.form_updated);
        });
    });

    self.form_updated = () => {
      self.data.registration_auto_approve = $(self.refs.registration_auto_approve).prop("checked");
      self.data.allow_robot_submissions = $(self.refs.allow_robot_submissions).prop("checked");
      self.data.terms = self.markdown_editor.value();

      let whitelist_emails_content = self.markdown_editor_whitelist.value();
      let email_addresses =
        whitelist_emails_content.trim() === ""
          ? []
          : whitelist_emails_content
              .split("\n")
              .map((email) => email.trim());

      let problematicEmailIndexes = [];
      email_addresses.forEach((email, index) => {
        if (!self.isValidEmail(email)) {
          problematicEmailIndexes.push(index);
        }
      });

      const errorDiv = self.root.querySelector(".error-message");
      if (problematicEmailIndexes.length > 0) {
        errorDiv.classList.add("ui", "red", "message");

        const errorMessage = document.createElement("strong");
        errorMessage.textContent = "One or more email addresses are invalid";
        errorDiv.innerHTML = "";
        errorDiv.appendChild(errorMessage);

        const errorList = document.createElement("ul");

        problematicEmailIndexes.forEach((index) => {
          const problematicEmail = email_addresses[index];
          const listItem = document.createElement("li");
          listItem.textContent = `${problematicEmail}`;
          errorList.appendChild(listItem);
        });

        errorDiv.appendChild(errorList);
      } else {
        errorDiv.classList.remove("ui", "red", "message");
        errorDiv.textContent = "";
      }

      if (problematicEmailIndexes.length === 0) {
        self.data.whitelist_emails = email_addresses;
      }

      let is_valid_emails = problematicEmailIndexes.length === 0;
      let is_valid_terms = !!self.data.terms;
      let is_valid = is_valid_terms && is_valid_emails;

      CODALAB.events.trigger("competition_is_valid_update", "participation", is_valid);

      if (is_valid) {
        CODALAB.events.trigger("competition_data_update", self.data);
      }
    };

    self.isValidEmail = function (email) {
      const emailPattern = /^[a-zA-Z0-9._-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,4}$/;
      return emailPattern.test(email);
    };

    CODALAB.events.on("competition_loaded", function (competition) {
      self.refs.registration_auto_approve.checked = competition.registration_auto_approve;
      self.refs.allow_robot_submissions.checked = competition.allow_robot_submissions;
      self.markdown_editor.value(competition.terms || "");

      self.markdown_editor_whitelist.value(
        Array.isArray(competition.whitelist_emails) &&
          competition.whitelist_emails.length > 0
          ? competition.whitelist_emails.join("\n")
          : ""
      );

      self.markdown_editor.codemirror.refresh();

      self.update();
      if ($ && $.fn && $.fn.checkbox) {
        $(".ui.checkbox", self.root).checkbox();
      }

      self.form_updated();
    });

    CODALAB.events.on("update_codemirror", () => {
      self.markdown_editor.codemirror.refresh();
    });
  </script>
</competition-participation>
