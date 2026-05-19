import React from "react";

type Context = { user_id: string; course_id: string; activity_id: string };

type PxcActivityProps = {
  context: Context;
  state: unknown;
  permission: string;
  pxcToken?: string;
  trusted?: boolean;
};

declare global {
  // eslint-disable-next-line @typescript-eslint/no-namespace
  namespace React.JSX {
    interface IntrinsicElements {
      "pxc-activity": React.DetailedHTMLProps<
        React.HTMLAttributes<HTMLElement> & {
          "data-context"?: string;
          "data-state"?: string;
          "data-permission"?: string;
          "data-src"?: string;
          "data-pxc-token"?: string;
          "data-trusted"?: string;
          embed?: string;
        },
        HTMLElement
      >;
    }
  }
}

export function PxcActivity({ context, state, permission, pxcToken, trusted }: PxcActivityProps) {
  return (
    <pxc-activity
      data-context={JSON.stringify(context)}
      data-state={JSON.stringify(state)}
      data-permission={permission}
      data-src={`/a/${context.activity_id}/ui.js`}
      data-pxc-token={pxcToken}
      data-trusted={trusted ? "1" : undefined}
      embed={pxcToken ? "native" : undefined}
    />
  );
}
